import { render, screen, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { it, expect, vi } from "vitest";
import { UploadPanel } from "./UploadPanel";
import { api } from "../api/client";
import { deferred, document } from "../test/fixtures";
it("shows upload state, filename, and actual ingestion metadata on success", async () => {
  const pending = deferred<typeof document>();
  vi.spyOn(api, "upload").mockReturnValue(pending.promise);
  const uploaded = vi.fn();
  render(<UploadPanel onUploaded={uploaded} />);
  await userEvent.upload(
    screen.getByLabelText("Choose document"),
    new File(["some text"], "sample.txt", { type: "text/plain" }),
  );
  expect(screen.getByText("Uploading & indexing…")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Browse files" })).toBeDisabled();
  await act(async () => pending.resolve(document));
  expect(screen.getByText("sample.txt is ready")).toBeInTheDocument();
  expect(screen.getByText(/2 chunks indexed/)).toBeInTheDocument();
  expect(
    screen.getByText(`document_id: ${document.document_id}`),
  ).toBeInTheDocument();
  expect(uploaded).toHaveBeenCalledWith(document);
});
it("handles drop upload and server errors without registering a failed document", async () => {
  const uploaded = vi.fn();
  vi.spyOn(api, "upload").mockRejectedValue(
    new Error("Document processing is unavailable."),
  );
  render(<UploadPanel onUploaded={uploaded} />);
  fireEvent.drop(
    screen.getByText("Drop your document here").closest(".dropzone")!,
    {
      dataTransfer: {
        files: [new File(["pdf"], "report.pdf", { type: "application/pdf" })],
      },
    },
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Document processing is unavailable.",
  );
  expect(uploaded).not.toHaveBeenCalled();
});
it("rejects multiple dropped documents clearly", () => {
  const upload = vi.spyOn(api, "upload");
  render(<UploadPanel onUploaded={vi.fn()} />);
  fireEvent.drop(
    screen.getByText("Drop your document here").closest(".dropzone")!,
    {
      dataTransfer: {
        files: [new File(["x"], "a.txt"), new File(["y"], "b.txt")],
      },
    },
  );
  expect(screen.getByRole("alert")).toHaveTextContent("one document at a time");
  expect(upload).not.toHaveBeenCalled();
});
