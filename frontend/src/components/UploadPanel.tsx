import { useRef, useState } from "react";
import { UploadCloud, CheckCircle2, LoaderCircle } from "lucide-react";
import { api, maxUploadMB } from "../api/client";
import { useRequest } from "../hooks/useRequest";
import type { Document } from "../types/api";
import { ErrorNotice } from "./ErrorNotice";
export function UploadPanel({
  onUploaded,
}: {
  onUploaded: (doc: Document) => void;
}) {
  const request = useRequest<Document>();
  const input = useRef<HTMLInputElement>(null);
  const [filename, setFilename] = useState("");
  const [dragging, setDragging] = useState(false);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  async function upload(files: FileList | null) {
    if (!files?.length || request.loading) return;
    setSelectionError(null);
    if (files.length !== 1) {
      setSelectionError("Please upload one document at a time.");
      return;
    }
    setFilename(files[0].name);
    const doc = await request.run((signal) => api.upload(files[0], signal));
    if (doc) onUploaded(doc);
  }
  return (
    <section className="upload-panel" aria-labelledby="upload-heading">
      <div className="section-label">
        <h2 id="upload-heading">Add a document</h2>
        <span>PDF / TXT</span>
      </div>
      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!request.loading) setDragging(true);
        }}
        onDragLeave={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node))
            setDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          void upload(e.dataTransfer.files);
        }}
      >
        <input
          ref={input}
          type="file"
          accept=".pdf,.txt,application/pdf,text/plain"
          aria-label="Choose document"
          disabled={request.loading}
          onChange={(e) => {
            void upload(e.target.files);
            e.target.value = "";
          }}
          className="file-input"
        />
        {request.loading ? (
          <LoaderCircle className="spin" size={26} />
        ) : (
          <UploadCloud size={27} strokeWidth={1.5} />
        )}
        <div>
          <strong>
            {request.loading
              ? "Uploading & indexing…"
              : "Drop your document here"}
          </strong>
          <p>
            {request.loading
              ? filename
              : `PDF or UTF-8 text · up to ${maxUploadMB} MB`}
          </p>
        </div>
        <button
          className="button secondary compact"
          disabled={request.loading}
          onClick={() => input.current?.click()}
        >
          Browse files
        </button>
      </div>
      {request.loading && (
        <div className="upload-progress" role="status">
          <span className="indeterminate" />
          Extracting text, creating chunks and indexing. This may take a moment.
        </div>
      )}
      <ErrorNotice message={selectionError || request.error} />
      {request.data && (
        <div className="upload-success" role="status">
          <CheckCircle2 size={19} />
          <div>
            <strong>{request.data.filename} is ready</strong>
            <p>
              {request.data.page_count === null
                ? "Text document"
                : `${request.data.page_count} ${request.data.page_count === 1 ? "page" : "pages"}`}{" "}
              <span>·</span> {request.data.indexed_chunk_count.toLocaleString()}{" "}
              {request.data.indexed_chunk_count === 1 ? "chunk" : "chunks"} indexed
            </p>
            <code>document_id: {request.data.document_id}</code>
          </div>
        </div>
      )}
    </section>
  );
}
