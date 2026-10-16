# Deployment checklist

These actions are operator tasks, not claims of an existing cloud deployment.

- [ ] Provision a Qdrant-compatible instance using your own account; confirm costs first.
- [ ] Set QDRANT_URL to the cluster HTTPS endpoint, without URL credentials.
- [ ] Set QDRANT_API_KEY as a backend secret if required; grant collection read/write access.
- [ ] Choose QDRANT_COLLECTION_NAME; do not use the benchmark collection for demo uploads.
- [ ] Create an empty collection with the embedding model's dimension and cosine distance, or bootstrap with a controlled first upload before switching the hosting probe to /ready. Default MiniLM uses 384 dimensions.
- [ ] Build/test the Linux amd64 backend image with Docker on your host or CI.
- [ ] Deploy one backend worker and one service replica; allow model downloads or attach a prepared cache.
- [ ] Set APP_ENV=production and DEBUG=false.
- [ ] Set PORT as required by the host and route traffic to it.
- [ ] Confirm Qdrant connectivity, network policy and outbound HTTPS access.
- [ ] Set HF_HOME to a persistent volume writable by UID 10001; use HF_HUB_OFFLINE only with a complete cache.
- [ ] /health returns 200.
- [ ] /ready returns 200 after collection setup; configure a probe timeout greater than the 10-second Qdrant client timeout.
- [ ] Configure LLM_PROVIDER, LLM_MODEL, LLM_BASE_URL and the LLM_API_KEY backend secret.
- [ ] Explicitly choose RETRIEVAL_STRATEGY (hybrid_rerank is the quality-first portfolio setting).
- [ ] Set explicit production CORS_ORIGINS; no wildcard or credentials.
- [ ] Build/deploy frontend with VITE_API_BASE_URL set to the real backend HTTPS origin.
- [ ] Verify PDF/TXT upload, ingestion metadata and document scope.
- [ ] Verify /search and inspect ranked source metadata.
- [ ] Manually test /ask with your own provider budget; verify citations render.
- [ ] Inspect X-Request-ID and JSON request logs; confirm no content or secrets appear.
- [ ] Confirm secrets/.env, corpus files and local vector stores are absent from Git and image layers.
- [ ] Use host-level restricted access, traffic limits and provider spending limits for the unauthenticated demo.
- [ ] Check memory, CPU, cold starts and upload limits under representative load; do not infer production sizing from the small benchmark.
- [ ] Verify SIGTERM shutdown, container healthcheck and model-volume permissions on the actual deployment host.

No cloud resources, accounts or secrets were created by this deployment-readiness work.
