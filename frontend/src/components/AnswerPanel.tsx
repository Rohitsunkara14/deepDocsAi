import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { visit } from "unist-util-visit";
import type { Root, Text, Link } from "mdast";
import { BookOpen, Check, FileText, MessageSquareText } from "lucide-react";
import type { Answer } from "../types/api";
function citationLinks(numbers: Set<number>) {
  return () => (tree: Root) => {
    visit(tree, "text", (node: Text, index, parent) => {
      if (!parent || index === undefined || parent.type === "link") return;
      const parts: (Text | Link)[] = [];
      let start = 0;
      for (const match of node.value.matchAll(/\[(\d+)\]/g)) {
        const number = Number(match[1]);
        if (!numbers.has(number)) continue;
        if (match.index > start)
          parts.push({
            type: "text",
            value: node.value.slice(start, match.index),
          });
        parts.push({
          type: "link",
          url: `#source-${number}`,
          children: [{ type: "text", value: match[0] }],
        });
        start = match.index + match[0].length;
      }
      if (!parts.length) return;
      if (start < node.value.length)
        parts.push({ type: "text", value: node.value.slice(start) });
      parent.children.splice(index, 1, ...parts);
      return index + parts.length;
    });
  };
}
export function AnswerPanel({
  answer,
  loading,
}: {
  answer: Answer | null;
  loading: boolean;
}) {
  const [active, setActive] = useState<number | null>(null);
  const citations = answer?.citations ?? [];
  function highlight(number: number) {
    setActive(number);
    const card = document.getElementById(`source-${number}`);
    card?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    card?.focus({ preventScroll: true });
  }
  return (
    <div className="answer-layout">
      <section
        className="answer-panel"
        aria-labelledby="answer-heading"
        aria-busy={loading}
      >
        <div className="section-label">
          <h2 id="answer-heading">
            <MessageSquareText size={18} />
            Research answer
          </h2>
          {answer && <span className="result-badge">Response received</span>}
        </div>
        {loading ? (
          <div className="answer-loading" role="status">
            <div className="skeleton" />
            <div className="skeleton" />
            <div className="skeleton short" />
            <p>Finding evidence and preparing your answer…</p>
          </div>
        ) : answer ? (
          <>
            <p className="answered-question">{answer.question}</p>
            <div className="answer-text">
              <ReactMarkdown
                remarkPlugins={[
                  citationLinks(new Set(citations.map((c) => c.source_number))),
                ]}
                components={{
                  a: ({ href, children }) => {
                    const number = Number(href?.replace("#source-", ""));
                    return href?.startsWith("#source-") &&
                      citations.some((c) => c.source_number === number) ? (
                      <button
                        className="citation-marker"
                        aria-label={`Show source ${number}`}
                        onClick={() => highlight(number)}
                      >
                        {children}
                      </button>
                    ) : (
                      <span>{children}</span>
                    );
                  },
                  img: ({ alt }) => <span>{alt}</span>,
                }}
              >
                {answer.answer}
              </ReactMarkdown>
            </div>
            <div className="answer-footer">
              <Check size={14} />
              {citations.length
                ? "Citations supplied by the backend · verify important claims in the source"
                : "No citations returned for this answer"}
            </div>
          </>
        ) : (
          <div className="answer-empty">
            <span className="empty-icon">
              <BookOpen size={28} strokeWidth={1.4} />
            </span>
            <h3>From documents to understanding.</h3>
            <p>
              Ask a question to turn your source material into an answer with
              traceable evidence.
            </p>
            <div className="empty-steps">
              <span>Ask a question</span>
              <i /> <span>Find evidence</span>
              <i />
              <span>Follow the citations</span>
            </div>
          </div>
        )}
      </section>
      <aside className="sources-panel" aria-labelledby="sources-heading">
        <div className="section-label">
          <h2 id="sources-heading">Sources</h2>
          <span className="count">{citations.length}</span>
        </div>
        {!citations.length ? (
          <div className="sources-empty">
            <FileText size={25} strokeWidth={1.3} />
            <p>Your evidence, in context.</p>
            <span>Source references appear here with each cited answer.</span>
          </div>
        ) : (
          <>
            <p className="sources-hint">
              Select an answer marker to highlight its source.
            </p>
            {citations.map((c) => (
              <article
                id={`source-${c.source_number}`}
                tabIndex={-1}
                key={`${c.source_number}-${c.chunk_id}`}
                className={`source-card ${active === c.source_number ? "active" : ""}`}
              >
                <div className="source-heading">
                  <span className="source-number">{c.source_number}</span>
                  <FileText size={16} />
                </div>
                <h3>{c.source_filename}</h3>
                <p>
                  {c.page_number === null
                    ? "Page not available (TXT)"
                    : `Page ${c.page_number}`}{" "}
                  <span>·</span> Chunk {c.chunk_index}
                </p>
                <code title={c.chunk_id}>{c.chunk_id}</code>
              </article>
            ))}
            <p className="source-disclaimer">
              References only. Original files are not stored by the backend.
            </p>
          </>
        )}
      </aside>
    </div>
  );
}
