import json
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.core.config import Settings
from app.main import create_app
from app.services.indexing import create_resources


def test_ready(resources):
    app=create_app(Settings(_env_file=None),resources)
    with TestClient(app) as c:
        assert c.get('/health').status_code==200
        assert c.get('/ready').status_code==503
        resources.store.ensure_collection(3)
        with patch.object(resources.embedder,'embed_text',side_effect=AssertionError('inference forbidden')):
            assert c.get('/ready').status_code==200
        with patch.object(resources.store,'check_ready',side_effect=RuntimeError('SECRET')):
            response=c.get('/ready'); assert response.status_code==503 and 'SECRET' not in response.text
        app.state.initialized=False
        assert c.get('/ready').json()['reason']=='application_initializing'


@pytest.mark.parametrize('incoming',['trace-123_ok','bad value','x'*65,''])
def test_request_id(resources,incoming):
    with TestClient(create_app(Settings(_env_file=None),resources)) as c:
        value=c.get('/health',headers={'X-Request-ID':incoming}).headers['x-request-id']
        assert 0<len(value)<=64
        assert (value==incoming)==(incoming=='trace-123_ok')


def test_logs_and_safe_errors(resources,caplog):
    caplog.set_level('INFO',logger='uvicorn.error.deepdocs.requests')
    class StubLLM:
        async def generate(self,*args): return 'Revenue rose. [1]'
    app=create_app(Settings(_env_file=None),resources,StubLLM())
    @app.get('/test-failure')
    def fail(): raise RuntimeError('PRIVATEBODY SECRETKEY')
    with TestClient(app) as c:
        c.post('/documents/upload',files={'file':('private.txt',b'PRIVATEBODY revenue','text/plain')})
        assert c.post('/ask?private=PRIVATEQUERY',json={'question':'PRIVATEQUERY revenue'},headers={'X-Request-ID':'ask-one'}).status_code==200
        failure=c.get('/test-failure',headers={'Origin':'http://localhost:5173'})
        assert failure.status_code==500 and 'SECRETKEY' not in failure.text
        assert failure.headers['x-request-id'] and failure.headers['access-control-allow-origin']=='http://localhost:5173'
        c.get('/PRIVATEQUERY?secret=SECRETKEY')
    events=[json.loads(r.message) for r in caplog.records if r.name.endswith('.requests')]
    row=next(r for r in events if r['request_id']=='ask-one')
    assert row['retrieval_latency_ms']>=0 and row['generation_latency_ms']>=0
    assert row['retrieved_chunk_count']==1 and row['generation_success']
    assert row['path']=='/ask' and events[-1]['path']=='<unmatched>'
    assert not any(s in caplog.text for s in ['PRIVATEQUERY','PRIVATEBODY','SECRETKEY'])


def test_qdrant_secret_and_transport():
    config=Settings(_env_file=None,qdrant_url='https://cluster.example:6333',qdrant_api_key='TOP-SECRET')
    assert 'TOP-SECRET' not in repr(config)
    with patch('app.services.indexing.QdrantClient') as client:
        create_resources(config).close()
        assert client.call_args.kwargs['api_key']=='TOP-SECRET'
        assert client.call_args.kwargs['follow_redirects'] is False
    with patch('app.services.indexing.QdrantClient') as client:
        create_resources(Settings(_env_file=None)).close()
        assert client.call_args.kwargs['api_key'] is None
    with patch('app.services.indexing.QdrantClient') as client:
        create_resources(Settings(_env_file=None,qdrant_local_path=':memory:')).close()
        assert client.call_args.kwargs=={'path':':memory:'}


@pytest.mark.parametrize('values',[
    {'app_env':'production','debug':True},{'cors_origins':['*']},
    {'cors_origins':['https://user:SECRET@domain.example']},
    {'qdrant_url':'https://user:SECRET@domain.example'},
    {'qdrant_url':'https://domain.example?api_key=SECRET'},
    {'qdrant_url':'http://domain.example','qdrant_api_key':'SECRET'},
])
def test_safety_settings(values):
    with pytest.raises(ValidationError) as error: Settings(_env_file=None,**values)
    assert 'SECRET' not in str(error.value)


def test_cors(resources):
    with TestClient(create_app(Settings(_env_file=None,cors_origins=['http://localhost:5173','https://portfolio.example']),resources)) as c:
        response=c.options('/ask',headers={'Origin':'https://portfolio.example','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'x-request-id,content-type'})
        assert response.status_code==200 and response.headers['x-request-id']
        assert 'access-control-allow-credentials' not in response.headers
        assert c.get('/health',headers={'Origin':'https://portfolio.example'}).headers['access-control-expose-headers']=='X-Request-ID'
        assert 'access-control-allow-origin' not in c.get('/health',headers={'Origin':'https://evil.example'}).headers


def test_entrypoint(monkeypatch):
    import start
    monkeypatch.setenv('PORT','8123')
    with patch.object(start.uvicorn,'run') as run:
        start.main(); opts=run.call_args.kwargs
        assert opts['port']==8123 and opts['workers']==1 and not opts['reload'] and not opts['access_log']
    monkeypatch.setenv('PORT','0')
    with pytest.raises(ValueError): start.main()


def test_qdrant_authenticated_http_transport_never_redirects():
    import httpx
    from qdrant_client import QdrantClient
    from qdrant_client.http.exceptions import UnexpectedResponse
    seen=[]
    def handler(request):
        seen.append(request)
        if len(seen)==1:
            return httpx.Response(200,json={"result":{"exists":True},"status":"ok","time":0})
        return httpx.Response(307,headers={"Location":"https://other.example/"})
    client=QdrantClient(url='https://cluster.example',api_key='FAKE-KEY',check_compatibility=False,
                        follow_redirects=False,transport=httpx.MockTransport(handler))
    try:
        assert client.collection_exists('demo')
        assert seen[0].headers['api-key']=='FAKE-KEY'
        with pytest.raises(UnexpectedResponse): client.collection_exists('demo')
        assert len(seen)==2 and all(req.url.host=='cluster.example' for req in seen)
    finally: client.close()
