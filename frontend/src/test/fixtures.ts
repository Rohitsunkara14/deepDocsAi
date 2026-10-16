import type { Answer, Document, SearchResponse } from "../types/api";
// Synthetic test data, never rendered as live results or used for benchmark labels.
export const document: Document = {
  document_id: "11111111-1111-4111-8111-111111111111",
  filename: "sample.txt",
  content_type: "text/plain",
  page_count: null,
  chunk_count: 2,
  indexed_chunk_count: 2,
};
export const answer: Answer = {
  question: "What does the sample say?",
  answer: "The sample describes a test workflow. [1]",
  citations: [
    {
      source_number: 1,
      chunk_id: "test-chunk-1",
      document_id: document.document_id,
      source_filename: document.filename,
      page_number: null,
      chunk_index: 0,
    },
  ],
};
export const search: SearchResponse = {
  query: answer.question,
  results: [
    {
      ...answer.citations[0],
      text: "Synthetic workflow example.",
      score: 0.23456,
    },
  ],
};
export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
}
