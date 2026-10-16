import { Files, FileText, Layers3, ShieldCheck } from "lucide-react";
import type { Document } from "../types/api";
export function DocumentSidebar({
  documents,
  selected,
  onSelect,
}: {
  documents: Document[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  return (
    <aside className="document-sidebar">
      <div className="sidebar-title">
        <span>YOUR LIBRARY</span>
        <span className="count">{documents.length}</span>
      </div>
      <button
        className={`document-option all ${!selected ? "selected" : ""}`}
        aria-pressed={!selected}
        onClick={() => onSelect("")}
      >
        <Layers3 size={18} />
        <span>
          All documents<small>Search the connected index</small>
        </span>
      </button>
      <div className="document-list">
        {documents.length ? (
          documents.map((doc) => (
            <button
              key={doc.document_id}
              className={`document-option ${selected === doc.document_id ? "selected" : ""}`}
              aria-pressed={selected === doc.document_id}
              onClick={() => onSelect(doc.document_id)}
            >
              <FileText size={19} />
              <span className="document-info">
                <strong>{doc.filename}</strong>
                <small>
                  {doc.indexed_chunk_count.toLocaleString()} indexed {doc.indexed_chunk_count === 1 ? "chunk" : "chunks"}
                </small>
                <code>{doc.document_id}</code>
              </span>
            </button>
          ))
        ) : (
          <div className="library-empty">
            <Files size={27} strokeWidth={1.3} />
            <p>Your research starts here.</p>
            <span>Upload a document to add it to this session’s library.</span>
          </div>
        )}
      </div>
      <div className="session-note">
        <ShieldCheck size={17} />
        <p>
          Library list stays in this session. Refreshing clears the list, not
          the backend index.
        </p>
      </div>
      <div className="strategy-note">
        <span className="eyebrow">PORTFOLIO STRATEGY</span>
        <strong>Hybrid + Cross-Encoder Reranking</strong>
        <p>
          Documented benchmark choice. The running server controls its retrieval
          mode.
        </p>
      </div>
    </aside>
  );
}
