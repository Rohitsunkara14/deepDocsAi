import { describe, it, expect, vi } from "vitest";
import { createApi, validateFile } from "./client";
import { answer, document, search } from "../test/fixtures";
const response = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
describe("API contracts", () => {
  it("parses /ask and sends only question, top_k and explicit scope", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(answer));
    const client = createApi("http://localhost:8000/", fetcher);
    expect(
      await client.ask({
        question: answer.question,
        top_k: 5,
        document_id: document.document_id,
      }),
    ).toEqual(answer);
    expect(fetcher.mock.calls[0][0]).toBe("http://localhost:8000/ask");
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
      question: answer.question,
      top_k: 5,
      document_id: document.document_id,
    });
  });
  it("maps the search query and omits the all-documents filter", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(search));
    await createApi("http://localhost:8000", fetcher).search({
      question: "workflow",
      top_k: 3,
    });
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
      query: "workflow",
      top_k: 3,
    });
  });
  it("normalizes missing MIME, uses multipart without overriding its boundary", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(document));
    const client = createApi("http://localhost:8000", fetcher);
    expect(await client.upload(new File(["data"], "sample.txt"))).toEqual(
      document,
    );
    const init = fetcher.mock.calls[0][1];
    expect(init.headers).toBeUndefined();
    expect(init.body.get("file").type).toBe("text/plain");
  });
  it.each([
    {},
    { ...answer, citations: [{ ...answer.citations[0], chunk_index: -1 }] },
  ])("rejects malformed successful responses", async (body) => {
    const client = createApi(
      "http://localhost:8000",
      vi.fn().mockResolvedValue(response(body)),
    );
    await expect(
      client.ask({ question: "question", top_k: 5 }),
    ).rejects.toMatchObject({ code: "response" });
  });
  it("rejects non-JSON responses without displaying raw HTML", async () => {
    const client = createApi(
      "http://localhost:8000",
      vi.fn().mockResolvedValue(new Response("<html>internal trace</html>")),
    );
    await expect(client.health()).rejects.toMatchObject({ code: "response" });
  });
  it.each([
    [503, "LLM generation is not configured. Set LLM_API_KEY.", "llm"],
    [503, "Qdrant unavailable", "unavailable"],
    [504, "Timeout", "timeout"],
    [409, "collection mismatch", "index"],
    [422, [{ msg: "wrong" }], "validation"],
    [500, "private stack trace", "server"],
  ])("maps HTTP %s into a safe error", async (status, detail, code) => {
    const client = createApi(
      "http://localhost:8000",
      vi.fn().mockResolvedValue(response({ detail }, Number(status))),
    );
    await expect(
      client.ask({ question: "question", top_k: 5 }),
    ).rejects.toMatchObject({ code });
  });
  it("reports an unreachable backend", async () => {
    await expect(
      createApi(
        "http://localhost:8000",
        vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
      ).health(),
    ).rejects.toMatchObject({ code: "network" });
  });
  it("rejects invalid base URL configuration", async () => {
    await expect(
      createApi("javascript:alert(1)").health(),
    ).rejects.toMatchObject({ code: "configuration" });
  });
  it("bounds request time and aborts transport", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) =>
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          ),
        ),
    );
    const expectation = expect(
      createApi("http://localhost:8000", fetcher).health(),
    ).rejects.toMatchObject({ code: "timeout" });
    await vi.advanceTimersByTimeAsync(5001);
    await expectation;
    expect(fetcher.mock.calls[0][1]?.signal?.aborted).toBe(true);
  });
});
describe("file validation", () => {
  it.each([
    new File(["x"], "report.csv", { type: "text/csv" }),
    new File([], "empty.txt"),
    new File(["x"], "report.pdf", { type: "image/png" }),
  ])("rejects invalid files", (file) =>
    expect(() => validateFile(file)).toThrow(),
  );
  it("enforces size before network transmission", () => {
    expect(() =>
      validateFile(new File(["12345"], "file.txt"), 4 / 1024 / 1024),
    ).toThrow("exceeds");
  });
  it("accepts uppercase supported extensions and missing MIME", () =>
    expect(() => validateFile(new File(["test"], "REPORT.PDF"))).not.toThrow());
});

it("rejects a MIME and extension mismatch", () => { expect(() => validateFile(new File(["text"], "report.pdf", { type: "text/plain" }))).toThrow("Choose a PDF"); });
