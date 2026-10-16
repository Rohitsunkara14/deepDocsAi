import { apiBaseUrl } from "./config";
import { z } from "zod";
import { askSchema, ingestionSchema, searchSchema } from "../types/api";
import type { QueryInput } from "../types/api";
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly code = "request",
  ) {
    super(message);
    this.name = "ApiError";
  }
}
const configuredLimit = Number(import.meta.env.VITE_MAX_UPLOAD_SIZE_MB ?? 10);
export const maxUploadMB =
  Number.isFinite(configuredLimit) && configuredLimit > 0
    ? configuredLimit
    : 10;
export function validateFile(file: File, limitMB = maxUploadMB) {
  const ext = file.name.split(".").pop()?.toLowerCase();
  if (
    !["pdf", "txt"].includes(ext ?? "") ||
    (file.type &&
      file.type !== (ext === "pdf" ? "application/pdf" : "text/plain"))
  )
    throw new ApiError("Choose a PDF or UTF-8 TXT file.", "file");
  if (file.size === 0)
    throw new ApiError(
      "This file is empty. Choose a document with text.",
      "file",
    );
  if (file.size > limitMB * 1024 * 1024)
    throw new ApiError(
      `This file exceeds the ${limitMB} MB upload limit. Choose a smaller file.`,
      "file",
    );
}
function serverError(
  status: number,
  detail: unknown,
  action: string,
): ApiError {
  const text = typeof detail === "string" ? detail.toLowerCase() : "";
  if (/not configured|unconfigured|llm_model|llm_api_key/.test(text))
    return new ApiError(
      "Answer generation is not configured on the backend. Ask the server owner to configure the LLM; document search is still available.",
      "llm",
    );
  if (/timed out|timeout/.test(text) || status === 504)
    return new ApiError(
      "The server took too long to respond. Please try again.",
      "timeout",
    );
  if (status === 413)
    return new ApiError(
      "This file exceeds the backend upload limit. Choose a smaller file.",
      "file",
    );
  if (status === 415)
    return new ApiError(
      "This file type is not supported. Choose a PDF or UTF-8 TXT file.",
      "file",
    );
  if (status === 400 || status === 422)
    return new ApiError(
      action === "upload"
        ? "The document could not be read. Check that it contains selectable text, is not encrypted, and TXT files use UTF-8."
        : "Check your question, document selection and source count, then try again.",
      "validation",
    );
  if (status === 409)
    return new ApiError(
      "The document index is incompatible with the server configuration. Ask the server owner to check the collection.",
      "index",
    );
  if (status === 503)
    return new ApiError(
      action === "ask"
        ? "Answer generation or retrieval is temporarily unavailable. Try search to check the available sources."
        : "Document processing or retrieval is temporarily unavailable. Check the backend model and document index, then retry.",
      "unavailable",
    );
  return new ApiError(
    `${action === "upload" ? "Upload" : action === "search" ? "Search" : "The request"} failed. Please try again.`,
    "server",
  );
}
export function createApi(
  baseUrl: string,
  transport: typeof fetch = (...args) => fetch(...args),
) {
  async function request<T>(
    path: string,
    schema: z.ZodType<T>,
    init: RequestInit,
    signal?: AbortSignal,
    timeout = 60000,
  ): Promise<T> {
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) controller.abort();
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeout);
    try {
      let url: URL;
      try {
        url = new URL(`${baseUrl.replace(/\/+$/, "")}${path}`);
        if (!["http:", "https:"].includes(url.protocol)) throw new Error();
      } catch {
        throw new ApiError(
          "The backend URL is invalid. Check VITE_API_BASE_URL and restart the frontend.",
          "configuration",
        );
      }
      const response = await transport(url.toString(), {
        ...init,
        signal: controller.signal,
        credentials: "omit",
      });
      let body: unknown;
      try {
        body = await response.json();
      } catch {
        if (!response.ok)
          throw serverError(response.status, null, path.split("/").pop()!);
        throw new ApiError(
          "The backend returned an unreadable response. Check the API URL and server version.",
          "response",
        );
      }
      if (!response.ok)
        throw serverError(
          response.status,
          typeof body === "object" && body
            ? (body as { detail?: unknown }).detail
            : null,
          path.split("/").pop()!,
        );
      const parsed = schema.safeParse(body);
      if (!parsed.success)
        throw new ApiError(
          "The backend response has an unexpected format. Check that the frontend and backend versions match.",
          "response",
        );
      return parsed.data;
    } catch (error) {
      if (timedOut)
        throw new ApiError(
          "The request timed out. Try again; large documents can take longer to process. A timed-out upload may still finish on the server.",
          "timeout",
        );
      if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
      if (error instanceof ApiError) throw error;
      throw new ApiError(
        "Cannot reach the backend. Check that FastAPI is running and allows this frontend origin in CORS_ORIGINS.",
        "network",
      );
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
    }
  }
  const json = (body: unknown): RequestInit => ({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return {
    health: (signal?: AbortSignal) =>
      request(
        "/health",
        z.object({ status: z.literal("ok"), service: z.string() }),
        {},
        signal,
        5000,
      ),
    upload: (file: File, signal?: AbortSignal) => {
      validateFile(file);
      // Browsers may omit MIME for dropped files; normalize only validated PDF/TXT extensions.
      const type = file.name.toLowerCase().endsWith(".pdf")
        ? "application/pdf"
        : "text/plain";
      const form = new FormData();
      form.append("file", new File([file], file.name, { type }));
      return request(
        "/documents/upload",
        ingestionSchema,
        { method: "POST", body: form },
        signal,
        180000,
      );
    },
    ask: (input: QueryInput, signal?: AbortSignal) =>
      request("/ask", askSchema, json(input), signal, 120000),
    search: (input: QueryInput, signal?: AbortSignal) =>
      request(
        "/search",
        searchSchema,
        json({
          query: input.question,
          top_k: input.top_k,
          ...(input.document_id ? { document_id: input.document_id } : {}),
        }),
        signal,
      ),
  };
}
export const api = createApi(
  apiBaseUrl(import.meta.env.VITE_API_BASE_URL, import.meta.env.DEV),
);
