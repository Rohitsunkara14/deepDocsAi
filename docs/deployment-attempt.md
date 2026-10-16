# Deployment attempt — 2026-09-12

Status: blocked before GitHub publication. No cloud service or paid resource was created.

## Preflight

- Backend: 265 passed, 3 skipped (two dependency deprecation warnings).
- Frontend: 35 passed, 1 skipped.
- Production frontend build passed with an explicit example API origin; it is not a live deployment build.
- Git initialized on main. Initial application commit: 792a55438244eab115b37656f5ebc2004cdeb427.
- All 137 tracked files checked for excluded artifacts; none of the local environments, PDFs, vector stores, model caches, dependencies, or generated build output were tracked.
- Obvious credential-pattern scan of tracked files found no matches. Broader scan candidates were reviewed as placeholders, invalid-URL fixtures, and a variable reference; this is not a comprehensive security audit.

## Connections and blocking action

GitHub authenticates as ayush01792, but ayush01792/deepdocs-ai returns 404. The available GitHub connector cannot create repositories. The user must create the public deepdocs-ai repository under ayush01792, initialized with a README so the connector has a default branch to update.

Render account access is available, but no workspace has been selected and no service created. Vercel team discovery returned an empty list; no frontend project was created. Qdrant Cloud has not been inspected or configured, and no LLM secret has been consumed.

## Docker and memory observations

Docker Desktop 29.7.2 is now installed. The existing Linux amd64 image built successfully, including all hash-pinned dependencies and CPU PyTorch 2.14.0. An isolated Docker configuration used anonymous access to public images after the default credential helper returned a macOS Keychain error; no credentials were copied or exposed.

The container smoke check remained in Docker's created state before application startup. It did not establish health, readiness, inference, shutdown, or the feasibility of a 512 MiB container; no OOM was observed. This is not a verified Render Docker deployment.

A separate native macOS CPU smoke test loading both configured models peaked at 623.5 MiB RSS. That measurement is not interchangeable with Linux/Render memory use. Render's current free and $7/month compute tiers offer 512 MB; the next memory tier is 2 GB at $25/month. See https://render.com/pricing and https://render.com/docs/compute-plans. No plan was purchased or selected, and exact production sizing remains unverified.

## Live verification

No live backend/frontend URL exists from this attempt. Public health, readiness, upload, search, ask, browser CORS, and cloud logs remain unverified. Benchmark data was not uploaded or changed. Application behavior and retrieval algorithms are unchanged.
