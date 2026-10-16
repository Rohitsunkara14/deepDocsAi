// @vitest-environment node
// Opt-in real FastAPI check. Run only against an isolated integration store.
import { it, expect } from "vitest";
import { createApi } from "./client";
it.skipIf(import.meta.env.VITE_RUN_LOCAL_INTEGRATION !== "1")(
  "integrates with real upload/search and unconfigured /ask",
  async () => {
    const client = createApi("http://127.0.0.1:8000");
    expect((await client.health()).status).toBe("ok");
    const doc = await client.upload(
      new File(
        [
          "Integration fixture: the observatory opens at nine and closes at six.",
        ],
        "ui-integration.txt",
        { type: "text/plain" },
      ),
    );
    expect(doc.indexed_chunk_count).toBeGreaterThan(0);
    const results = await client.search({
      question: "When does the observatory open?",
      top_k: 3,
      document_id: doc.document_id,
    });
    expect(results.results[0].document_id).toBe(doc.document_id);
    expect(results.results[0].text).toContain("observatory");
    await expect(
      client.ask({
        question: "When does the observatory open?",
        top_k: 3,
        document_id: doc.document_id,
      }),
    ).rejects.toMatchObject({ code: "llm" });
  },
  180000,
);
