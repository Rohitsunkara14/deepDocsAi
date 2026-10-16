import { z } from "zod";
const page = z.number().int().nonnegative().nullable();
const identity = {
  chunk_id: z.string().min(1),
  document_id: z.string().uuid(),
  source_filename: z.string().min(1),
  page_number: page,
  chunk_index: z.number().int().nonnegative(),
};
export const ingestionSchema = z.object({
  document_id: z.string().uuid(),
  filename: z.string().min(1),
  content_type: z.string(),
  page_count: page,
  chunk_count: z.number().int().nonnegative(),
  indexed_chunk_count: z.number().int().nonnegative(),
});
export const citationSchema = z.object({
  ...identity,
  source_number: z.number().int().positive(),
});
export const askSchema = z.object({
  question: z.string(),
  answer: z.string(),
  citations: z.array(citationSchema),
});
export const searchSchema = z.object({
  query: z.string(),
  results: z.array(
    z.object({ ...identity, text: z.string(), score: z.number().finite() }),
  ),
});
export type Document = z.infer<typeof ingestionSchema>;
export type Citation = z.infer<typeof citationSchema>;
export type Answer = z.infer<typeof askSchema>;
export type SearchResponse = z.infer<typeof searchSchema>;
export type QueryInput = {
  question: string;
  top_k: number;
  document_id?: string;
};
