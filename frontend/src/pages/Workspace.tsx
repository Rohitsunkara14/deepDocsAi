import { useEffect, useState } from "react";
import { ArrowUpRight, CircleHelp, RotateCw } from "lucide-react";
import { api } from "../api/client";
import { Brand } from "../components/Icon";
import { DocumentSidebar } from "../components/DocumentSidebar";
import { UploadPanel } from "../components/UploadPanel";
import { QueryPanel } from "../components/QueryPanel";
import { BenchmarkSection } from "../components/BenchmarkSection";
import { useRequest } from "../hooks/useRequest";
import type { Document } from "../types/api";
export function Workspace() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selected, setSelected] = useState("");
  const health = useRequest<{ status: "ok"; service: string }>();
  useEffect(() => {
    void health.run((signal) => api.health(signal));
  }, [health.run]);
  const filename = documents.find((d) => d.document_id === selected)?.filename;
  function addDocument(doc: Document) {
    setDocuments((prev) => [
      ...prev.filter((d) => d.document_id !== doc.document_id),
      doc,
    ]);
    setSelected(doc.document_id);
  }
  return (
    <>
      <header className="topbar">
        <a
          href="#workspace"
          className="brand-link"
          aria-label="DeepDocs AI workspace"
        >
          <Brand />
        </a>
        <nav aria-label="Main navigation">
          <a className="nav-active" href="#workspace">
            Workspace
          </a>
          <a href="#benchmark">
            Architecture & benchmark <ArrowUpRight size={14} />
          </a>
        </nav>
        <button
          className={`connection ${health.data ? "online" : ""}`}
          title={
            health.error ||
            "Health check confirms API reachability, not model readiness. Click to refresh."
          }
          onClick={() => void health.run((signal) => api.health(signal))}
          disabled={health.loading}
        >
          {health.loading ? (
            <RotateCw size={13} className="spin" />
          ) : (
            <span className="status-dot" />
          )}
          {health.loading
            ? "Checking API"
            : health.data
              ? "API reachable"
              : "API unavailable"}
          <RotateCw size={12} />
        </button>
      </header>
      <div className="app-shell" id="workspace">
        <DocumentSidebar
          documents={documents}
          selected={selected}
          onSelect={setSelected}
        />
        <main>
          <div className="workspace-heading">
            <div>
              <span className="eyebrow">DOCUMENT RESEARCH WORKSPACE</span>
              <h1>A clearer view of your documents.</h1>
              <p>Production-style RAG document research assistant</p>
            </div>
            <span className="workspace-edition">
              DeepDocs AI <span>/</span> Portfolio edition
            </span>
          </div>
          <UploadPanel onUploaded={addDocument} />
          <QueryPanel selected={selected} filename={filename} />
          <BenchmarkSection />
          <footer>
            <Brand small />
            <span>Built for answers you can trace.</span>
            <a href="#benchmark">
              <CircleHelp size={14} />
              How it works
            </a>
          </footer>
        </main>
      </div>
    </>
  );
}
