# Deployment readiness verification — 2026-09-12

## Results

- Backend full suite: **265 passed, 3 opt-in tests skipped**. No cloud account, network or paid LLM inference required. Two existing Starlette/httpx/AnyIO deprecation warnings.
- Frontend full suite: **35 passed, 1 opt-in live-backend test skipped**.
- Frontend production build: **passed** with an explicit placeholder HTTPS API URL; missing URL intentionally fails before bundling. Configure the real URL and rebuild before deployment. Two non-blocking third-party Zod comment warnings remain.
- Dependency audit after adding Node build types: **0 npm vulnerabilities**.
- Linux amd64/Python 3.11 lock: 63 exact hash-pinned packages, CPU PyTorch, no NVIDIA runtime packages; generated using PyPI and official PyTorch CPU metadata. Docker installs wheels only with hash enforcement.
- Compose YAML parsed; existing backend + Qdrant services and named volumes preserved, explicit CORS added.
- Real non-container startup: PORT=18080, production mode, in-memory isolated Qdrant; /health 200 with supplied request ID; /ready 503 for absent collection; graceful application shutdown observed on interrupt. No model inference or paid request occurred.
- Readiness tests cover initialized/missing/inaccessible collections, with model inference prohibited.
- Logging tests cover IDs, unknown paths/query redaction, stage metadata, safe 500 responses and CORS headers.
- Qdrant auth tests include real client construction with a mock HTTP transport, API-key header forwarding, and rejection of cross-host redirects. No real cloud endpoint was called.
- Source/config patterns: no API-key/private-key patterns found in scanned application/frontend/docs files. No .git metadata exists here, so tracked-file/history secret auditing cannot be certified; repeat on the actual repository.

## Remaining manual verification

Docker is not installed in this environment. The actual Linux image build, wheel installation, non-root volume ownership, Docker healthcheck, container SIGTERM behavior and production cloud connectivity have not been executed. Dependency resolution is not a substitute for a container smoke test. Native entrypoint shutdown was checked with interrupt, not SIGTERM: direct signal delivery was unavailable in the execution sandbox.

No live LLM response was requested; operator /ask smoke testing requires their own provider credentials and budget. Model revisions remain those selected by existing settings; this work does not freeze model downloads or change retrieval behavior. Size CPU/memory using real workload measurements. Use a persistent single-replica backend and restricted demo exposure because app-level authentication/rate limiting is absent.

## Files changed

- backend/Dockerfile, backend/start.py, backend/requirements-docker.in, backend/requirements-linux.lock
- backend/.env.example, backend/.dockerignore
- backend/app/core/config.py, backend/app/core/observability.py
- backend/app/api/ready.py, backend/app/main.py
- backend/app/services/indexing.py, backend/app/services/search_service.py, backend/app/services/rag_service.py
- backend/app/rag/vector_store.py, backend/tests/test_deployment.py
- docker-compose.yml
- frontend/.env.example, frontend/vercel.json, frontend/vite.config.ts
- frontend/src/api/client.ts, frontend/src/api/config.ts, frontend/src/api/config.test.ts
- frontend/package.json, frontend/package-lock.json, frontend/tsconfig.json
- README.md, docs/deployment-checklist.md, docs/deployment-verification.md

No cloud resources were created. No authentication, memory, agents, databases or retrieval algorithms were added. Production ranking behavior and benchmark labels remain unchanged.
