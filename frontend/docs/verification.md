# Frontend verification — 2026-09-12

- Dependency installation and lockfile: complete; npm audit reports 0 vulnerabilities.
- Production build: TypeScript check and Vite build pass. Two non-blocking third-party Zod comment-annotation warnings are emitted by Rollup; it removes those comments.
- Default test suite: 32 passed, 1 opt-in integration test skipped.
- Opt-in real integration test: 1 passed separately using native Node File/FormData and real FastAPI.
- Live TXT ingestion and document-scoped search: passed through the frontend API client.
- Browser PDF upload: passed; response showed application document UUID, one page and one indexed chunk. Selecting it scoped the query.
- Browser search: returned the real PDF fixture text, rank 1, page 1, chunk index 0 and a retrieval score.
- Browser /ask: correctly rendered the backend LLM-unconfigured error. Successful answer/citation rendering and marker highlighting are covered by mocked component tests; no paid/live LLM generation was performed.
- CORS preflight for http://127.0.0.1:3000: HTTP 200 with the expected allow-origin header.
- Desktop preview inspected. At 390 CSS pixels, document scroll width remained 390, main content width 390 and question text 16px. Temporary viewport override restored.
- Frontend development server: http://127.0.0.1:3000/ (retained for the local preview).
- Temporary FastAPI integration server stopped after verification. Start the normal backend using the root README. Its LLM configuration is required for generated answers.

The isolated integration store was /private/tmp/deepdocs-ui-integration-20260910, collection deepdocs_ui_integration. It contains only synthetic TXT/PDF fixtures. Neither the normal production collection nor the real benchmark store was changed.

Scope: new frontend, root README and .gitignore only. Existing backend code, algorithms, retrieval defaults and evaluation labels are unchanged. Screenshot capture placeholders are documented in the root README; no fabricated screenshots or answers were added.
