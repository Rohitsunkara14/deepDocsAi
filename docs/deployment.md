# Deployment guide

Operational reference; Docker runtime remains locally unverified. See [checklist](deployment-checklist.md) and [verification](deployment-verification.md).


### Architecture

```text
Browser → static frontend host → persistent FastAPI Docker service
                                  ├─ external Qdrant / Qdrant Cloud
                                  ├─ OpenAI-compatible LLM provider (HTTPS)
                                  └─ local/cached SentenceTransformer + cross-encoder
```

The frontend and backend deploy independently. Qdrant stores vectors/text/metadata; embedding and reranking inference runs in FastAPI's process, not inside Qdrant. No new retrieval algorithms or services are required. The local BM25 cache is still process-owned: deploy **one Uvicorn worker and one backend replica**. Multiple independent writers/replicas can produce stale lexical caches and are outside this architecture's current guarantees.

### Required environment variables

Backend values are runtime environment variables; frontend values are public build-time values. The full local template remains `backend/.env.example`. Configure secrets through your host's secret manager, never through repository files or frontend variables.

| Variable | Deployment guidance / default |
|---|---|
| APP_ENV / DEBUG | `production` / `false`; production debug=true is rejected |
| PORT | Host-assigned port, otherwise `8000`; entrypoint binds `0.0.0.0` |
| CORS_ORIGINS | JSON array of exact frontend origins, e.g. `["https://your-frontend.example"]` |
| MAX_UPLOAD_SIZE_MB | `10`; align frontend limit and reverse-proxy body limits |
| CHUNKING_STRATEGY | `character` by default; existing `token` option remains available |
| CHUNK_SIZE / CHUNK_OVERLAP | `1000` / `150` for character chunks |
| TOKEN_CHUNK_SIZE / TOKEN_CHUNK_OVERLAP | `200` / `32`; overlap must be less than size |
| EMBEDDING_MODEL_NAME / EMBEDDING_BATCH_SIZE | `sentence-transformers/all-MiniLM-L6-v2` / `32` |
| QDRANT_URL | External cluster HTTP(S) URL; HTTPS required when API key is configured |
| QDRANT_API_KEY | Optional backend secret; empty for unauthenticated local Qdrant |
| QDRANT_COLLECTION_NAME | Application collection, default `deepdocs_chunks` |
| QDRANT_LOCAL_PATH | Leave unset for cloud/server mode; otherwise it takes precedence over URL |
| RETRIEVAL_STRATEGY | Set `hybrid_rerank` for quality-first portfolio use; application default stays `dense` |
| RETRIEVAL_CANDIDATE_COUNT / RRF_CONSTANT | `20` / `60` |
| RERANKER_MODEL_NAME | `cross-encoder/ms-marco-MiniLM-L6-v2` |
| RERANK_CANDIDATE_COUNT / RERANKER_BATCH_SIZE | `20` / `16` |
| LLM_PROVIDER / LLM_MODEL | `openai_compatible` / your accessible provider model identifier |
| LLM_API_KEY / LLM_BASE_URL | Backend secret / provider API base URL; default base is `https://api.openai.com/v1` |
| LLM_TEMPERATURE / LLM_MAX_OUTPUT_TOKENS | `0.1` / `800` |
| LLM_TIMEOUT_SECONDS | `30`; no paid retries are added |
| RAG_TOP_K_DEFAULT / RAG_MAX_CONTEXT_CHARS | `5` / `12000` |
| HF_HOME | Container default `/home/appuser/.cache/huggingface`; attach persistent storage owned by UID 10001 |
| HF_HUB_OFFLINE | Optional `1` only after all selected models are cached; otherwise leave unset or `0` |
| VITE_API_BASE_URL | Public backend URL, required for every frontend production build |
| VITE_MAX_UPLOAD_SIZE_MB | Browser limit, default `10`; server limit is authoritative |

### Backend deployment

Use a persistent Docker web service on Render, Railway, Fly.io or another Docker-compatible host. For example, Render can build from the repository Dockerfile; set the service root to `backend`, Dockerfile to `Dockerfile`, configure environment variables/secrets and a persistent cache volume. Leave the start-command override empty: the image runs `python start.py`. The process uses `PORT`, one worker, no reload, no raw Uvicorn access logs and a 30-second graceful-shutdown window. Give the host at least 40 seconds before force-killing it. Synchronous inference already in progress may not be interruptible immediately. See [Render Docker documentation](https://render.com/docs/docker) and [health-check configuration](https://render.com/docs/health-checks).

Build from the repository root:

```bash
docker build --platform linux/amd64 -t deepdocs-ai-backend ./backend
```

The image uses non-root UID 10001 and Python 3.11.14. The Linux amd64 dependency lock pins transitive versions and hashes, including a CPU PyTorch wheel, and installs with `--require-hashes`. `requirements.txt` remains the local-development range specification. The base tag is patch-pinned, not digest-pinned; OS-layer byte-for-byte reproducibility requires pinning the image digest in your release pipeline. ARM builds require a separately resolved/tested lock; do not assume the amd64 lock is portable.

To regenerate the lock deliberately (then test the resulting image):

```bash
cd backend
uv pip compile requirements-docker.in --python-version 3.11 \
  --python-platform x86_64-unknown-linux-gnu \
  --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match \
  --generate-hashes --emit-index-url --output-file requirements-linux.lock
```

Resolution trusts PyPI and the official PyTorch CPU index; committed hashes constrain actual installation artifacts. Docker is not available in the current development environment, so container image build, container healthcheck, Linux wheel installation and container-level SIGTERM handling must be verified on your Docker host/CI before publication.

### Frontend deployment

Use any static host. With Vercel, import your repository, select root directory `frontend`, install with `npm ci`, build with `npm run build`, and publish `dist`. Minimal `frontend/vercel.json` records these values; it introduces no application dependency. Set `VITE_API_BASE_URL` to the deployed backend HTTPS URL **before building**. Redeploy after changing it. See [Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite).

```bash
cd frontend
npm ci
VITE_API_BASE_URL=https://your-backend.example npm run build
```

Production builds fail if the API URL is missing or contains credentials/query/fragment. There is no production localhost fallback. Copying `.env.example` is sufficient for local build/preview, but replace its localhost URL for a hosted build. No rewrite rules are needed for the current single-page, hash-navigation UI. `VITE_` values are visible to users; never put Qdrant or LLM secrets in them. Fonts currently load from Google Fonts with local system-font fallbacks.

### Qdrant setup

Provision the instance yourself, obtain its cluster endpoint and create an appropriately scoped database API key if authentication is enabled. Configure `QDRANT_URL`, `QDRANT_API_KEY` and `QDRANT_COLLECTION_NAME` only on the backend. The client sends the API key separately, rejects embedded URL credentials and follows no HTTP redirects. Local no-key Qdrant and embedded storage continue to work. See [Qdrant Cloud authentication](https://qdrant.tech/documentation/cloud/authentication/).

Create the intended collection with cosine distance and the selected embedding dimension (384 for the default MiniLM), or perform a controlled first upload through the existing ingestion route, which creates it. `/ready` intentionally returns 503 until the collection exists. For hosts that withhold traffic until readiness succeeds, pre-create the collection or temporarily use `/health` during controlled initialization and switch to `/ready` afterward. Readiness never creates a collection. The benchmark collection remains isolated; do not route ordinary demo uploads into it.

### LLM setup

Use the existing OpenAI-compatible adapter and your own provider/model/key. Ingestion and search do not require LLM credentials. `/ask` reports a safe 503 when generation is unconfigured or fails. The adapter rejects URL credentials, does not follow credential-bearing redirects and does not expose provider response bodies. Use HTTPS for a hosted provider. No paid calls are made by ordinary tests; a real generation smoke test requires your own credentials and budget and is a manual deployment-checklist item.

### CORS

Credentials remain disabled. Origins are exact HTTP(S) scheme/host/port values without paths or wildcard entries. For development the defaults include `http://localhost:3000`, `http://127.0.0.1:3000` and `http://localhost:5173`. The frontend still defaults to port 3000; `npm run dev -- --port 5173` is also supported.

```dotenv
CORS_ORIGINS=["https://your-frontend.example"]
```

If local access is needed as well, explicitly add the local origin. An incoming `X-Request-ID` is allowed; the response header is exposed to the frontend. CORS is not authentication and does not prevent direct HTTP clients from calling the API.

### Health vs readiness

- `GET /health`: lightweight process liveness, unchanged. No model loading, Qdrant check or LLM request. Docker's healthcheck uses this endpoint and the configured PORT.
- `GET /ready`: 200 when lifespan initialization completed and configured collection metadata is accessible; otherwise safe 503. It does not perform embedding inference, paid generation, corpus scanning or collection creation. Remote Qdrant calls use a 10-second client timeout; allow suitable probe headroom.

Readiness checks connectivity/accessibility, not embedding-dimension compatibility, cache warmth, provider readiness or full answer quality. The ingestion/search pipeline continues to validate vector compatibility. Select the host's readiness probe deliberately to avoid restarts during a transient downstream outage.

### Operational logs

One `http_request` JSON event is logged per request with route template (or `<unmatched>`), method, status, total latency, success, configured retrieval strategy and request ID. Retrieval latency/chunk count and generation latency/success appear when those stages execute. These events can be aggregated by the hosting log service into request/error counts and latency distributions; no global metrics store or monitoring service is added.

Incoming IDs must be 1–64 ASCII letters/digits/dots/underscores/hyphens, starting with a letter or digit; otherwise a UUID is generated. Every response includes `X-Request-ID`, including handled failures/preflight. Query strings, unknown raw paths, request bodies, questions, prompts, chunks, document contents and API keys are not logged. Unexpected failures return a generic 500 without an exception traceback. Existing safe RAG stage events remain. The production entrypoint disables Uvicorn's separate access log because it includes raw URLs; use `--no-access-log` if starting Uvicorn yourself. Configure equivalent query/header redaction in your reverse proxy and hosting logs.

### Cold-start considerations

SentenceTransformer and cross-encoder downloads/loading can make first requests slow. A persistent CPU container/service with persistent HF_HOME is preferable to short-lived serverless functions. Offline mode is only valid with a complete cache, including tokenizer/config files and both models when reranking is enabled. HF_HOME and HF_HUB_OFFLINE are library process variables: export them in the shell or set them on the host/container; putting them only in backend/.env does not export them to Hugging Face. Neither health endpoint warms the models. Run a controlled ingestion/search smoke test to warm the serving process. Mounting a cache avoids downloads but does not eliminate process model-loading time.

Measure memory/CPU with representative input: embeddings and reranker each occupy memory; PDF parsing and upload spooling add peaks; the lexical index caches corpus text; larger batches and candidate counts increase load. Uploads are bounded before multipart spooling and again during file reading. Model downloads and Qdrant need outbound network access. CPU reranking is slower than dense retrieval in the development benchmark. No exact production RAM requirement has been measured or claimed. One worker/replica is a design constraint, not a scaling recommendation for an uncontrolled public service.

### Security limitations

This application has **no authentication**. Treat a public portfolio instance as a demo: use host-level restricted access, ingress request limits and provider budgets; do not expose upload/LLM endpoints to uncontrolled production traffic. CORS does not secure them. These hosting controls are operator responsibilities, not new application auth features. Original PDFs are not stored; extracted text is persisted in Qdrant, so only upload documents you are permitted to disclose/store.

Production DEBUG=true and wildcard origins are rejected. Secrets are SecretStr-backed where appropriate and are never rendered into frontend variables or request logs. `.env` files are ignored, Docker excludes local environment/corpus/store data, and no real keys are included in deployment examples. This checkout has no `.git` metadata, so actual tracked-file/history secret auditing must be repeated after importing it into your repository. Do not paste keys into commits or command history.

### Local vs production configuration

Local development keeps the existing Docker Compose Qdrant/backend workflow and native Vite frontend. Compose supplies explicit CORS, persistent Qdrant/model volumes and one backend process; its Qdrant is unauthenticated and bound to loopback. External/cloud deployment runs only the backend image against an external Qdrant URL; it does not deploy the local Compose Qdrant automatically.

Production-style local startup (from the repository root; preserve an existing backend/.env):

```bash
# First setup only, if no backend/.env exists:
cp backend/.env.example backend/.env
# Edit backend/.env locally; do not commit it.
docker compose --env-file backend/.env up --build -d
curl -f http://localhost:8000/health
# /ready will be 503 on a fresh store until the first document is ingested.

# In a second terminal:
cd frontend
npm ci
VITE_API_BASE_URL=http://localhost:8000 npm run build
npm run preview
```

Open `http://127.0.0.1:3000`, upload a supported document, then check `curl -f http://localhost:8000/ready`. Configure your LLM secrets only when you want to manually test generation. Stop any existing Vite dev server before previewing on the strict port. For development, use `npm run dev` instead; host-run FastAPI instructions earlier in this README remain available. `docker compose down` preserves named volumes.

Follow [the deployment checklist](../docs/deployment-checklist.md) before publication. Provisioning Qdrant, connecting a backend host/repository, assigning frontend hosting/domains and enabling live LLM generation require your external accounts and, where applicable, payment approval and secrets. No resources/accounts were created, no API keys requested and no paid calls were made during this step.
