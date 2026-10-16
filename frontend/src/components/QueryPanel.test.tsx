import { render, screen, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { QueryPanel } from "./QueryPanel";
import { api } from "../api/client";
import { answer, document, search, deferred } from "../test/fixtures";
it("submits scope/top_k, shows loading, then renders the returned answer", async () => {
  const pending = deferred<typeof answer>();
  const ask = vi.spyOn(api, "ask").mockReturnValue(pending.promise);
  render(
    <QueryPanel selected={document.document_id} filename={document.filename} />,
  );
  expect(screen.getByRole("button", { name: "Ask DeepDocs" })).toBeDisabled();
  await userEvent.type(
    screen.getByLabelText("What would you like to know?"),
    answer.question,
  );
  await userEvent.selectOptions(screen.getByLabelText("Source count"), "3");
  await userEvent.click(screen.getByRole("button", { name: "Ask DeepDocs" }));
  expect(ask).toHaveBeenCalledWith(
    { question: answer.question, top_k: 3, document_id: document.document_id },
    expect.any(AbortSignal),
  );
  expect(screen.getByRole("button", { name: "Researching…" })).toBeDisabled();
  await act(async () => pending.resolve(answer));
  expect(
    screen.getByText(/The sample describes a test workflow/),
  ).toBeInTheDocument();
});
it("renders friendly request errors and enables retry", async () => {
  vi.spyOn(api, "ask").mockRejectedValue(
    new Error("Answer generation is not configured on the backend."),
  );
  render(<QueryPanel selected="" />);
  fireEvent.change(screen.getByLabelText("What would you like to know?"), {
    target: { value: "question" },
  });
  await userEvent.click(screen.getByRole("button", { name: "Ask DeepDocs" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("not configured");
  expect(screen.getByRole("button", { name: "Ask DeepDocs" })).toBeEnabled();
});
it("discards late answers after document scope changes", async () => {
  const pending = deferred<typeof answer>();
  const ask = vi.spyOn(api, "ask").mockReturnValue(pending.promise);
  const view = render(<QueryPanel selected="" />);
  fireEvent.change(screen.getByLabelText("What would you like to know?"), {
    target: { value: "question" },
  });
  await userEvent.click(screen.getByRole("button", { name: "Ask DeepDocs" }));
  view.rerender(<QueryPanel selected={document.document_id} />);
  await act(async () => pending.resolve(answer));
  expect(ask.mock.calls[0][1]?.aborted).toBe(true);
  expect(
    screen.queryByText(/The sample describes a test workflow/),
  ).not.toBeInTheDocument();
});
it("uses /search independently and displays rank, score and raw chunk text", async () => {
  const fetchSearch = vi.spyOn(api, "search").mockResolvedValue(search);
  const ask = vi.spyOn(api, "ask");
  render(<QueryPanel selected="" />);
  fireEvent.change(screen.getByLabelText("What would you like to know?"), {
    target: { value: "workflow" },
  });
  await userEvent.click(screen.getByText("Retrieval explorer"));
  await userEvent.click(screen.getByRole("button", { name: "Run search" }));
  expect(
    await screen.findByText("Synthetic workflow example."),
  ).toBeInTheDocument();
  expect(screen.getByText("Score 0.2346")).toBeInTheDocument();
  expect(fetchSearch).toHaveBeenCalledWith(
    { question: "workflow", top_k: 5 },
    expect.any(AbortSignal),
  );
  expect(ask).not.toHaveBeenCalled();
});
