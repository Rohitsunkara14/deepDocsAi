import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  LoaderCircle,
  SlidersHorizontal,
  Search,
} from "lucide-react";
import { api } from "../api/client";
import { useRequest } from "../hooks/useRequest";
import type { Answer, SearchResponse } from "../types/api";
import { AnswerPanel } from "./AnswerPanel";
import { ErrorNotice } from "./ErrorNotice";
export function QueryPanel({
  selected,
  filename,
}: {
  selected: string;
  filename?: string;
}) {
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(5);
  const ask = useRequest<Answer>();
  const search = useRequest<SearchResponse>();
  useEffect(() => {
    ask.reset();
    search.reset();
  }, [selected, ask.reset, search.reset]);
  const valid = Boolean(question.trim()) && question.length <= 2000;
  const input = () => ({
    question: question.trim(),
    top_k: topK,
    ...(selected ? { document_id: selected } : {}),
  });
  return (
    <>
      <section className="question-panel">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (valid && !ask.loading)
              void ask.run((signal) => api.ask(input(), signal));
          }}
        >
          <div className="section-label">
            <label htmlFor="question">What would you like to know?</label>
            <span className="scope-label" title={filename}>
              {filename || "Across all documents"}
            </span>
          </div>
          <textarea
            id="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about a key finding, compare results, or explore a topic…"
            rows={3}
            maxLength={2000}
            required
          />
          <div className="question-controls">
            <div className="top-k">
              <label htmlFor="top-k">Source count</label>
              <select
                id="top-k"
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
              >
                {[1, 3, 5, 10, 15, 20].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
              <span>top_k</span>
            </div>
            <button
              className="button primary"
              type="submit"
              disabled={!valid || ask.loading}
            >
              {ask.loading ? (
                <>
                  <LoaderCircle size={17} className="spin" /> Researching…
                </>
              ) : (
                <>
                  Ask DeepDocs <ArrowUpRight size={18} />
                </>
              )}
            </button>
          </div>
          <ErrorNotice message={ask.error} />
        </form>
      </section>
      <AnswerPanel
        key={ask.data?.question ?? selected}
        answer={ask.data}
        loading={ask.loading}
      />
      <details className="debug-panel">
        <summary>
          <span>
            <SlidersHorizontal size={18} />
            Retrieval explorer <small>Advanced</small>
          </span>
          <span className="expand-label">Inspect sources +</span>
        </summary>
        <div className="debug-content">
          <div className="debug-intro">
            <div>
              <h3>Look behind the answer</h3>
              <p>
                Search using the question and scope above. Returns ranked chunks
                without calling the LLM.
              </p>
            </div>
            <button
              className="button secondary"
              disabled={!valid || search.loading}
              onClick={() =>
                void search.run((signal) => api.search(input(), signal))
              }
            >
              {search.loading ? (
                <LoaderCircle size={16} className="spin" />
              ) : (
                <Search size={16} />
              )}{" "}
              {search.loading ? "Searching…" : "Run search"}
            </button>
          </div>
          <ErrorNotice message={search.error} />
          {search.loading && <p role="status">Retrieving source chunks…</p>}
          {search.data && (
            <>
              <p className="search-query">Results for “{search.data.query}”</p>
              {!search.data.results.length && (
                <p className="no-results">
                  No matching chunks. Upload a document or try a different
                  question.
                </p>
              )}
              {search.data.results.map((hit, index) => (
                <article className="search-result" key={hit.chunk_id}>
                  <div className="search-result-heading">
                    <span className="rank">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <h4>{hit.source_filename}</h4>
                      <p>
                        {hit.page_number === null
                          ? "Page unavailable"
                          : `Page ${hit.page_number}`}{" "}
                        · Chunk {hit.chunk_index}
                      </p>
                    </div>
                    <code>Score {hit.score.toFixed(4)}</code>
                  </div>
                  <p className="chunk-text">{hit.text}</p>
                </article>
              ))}
              <p className="source-disclaimer">
                Scores depend on the server’s retrieval strategy. They are not
                confidence percentages.
              </p>
            </>
          )}
        </div>
      </details>
    </>
  );
}
