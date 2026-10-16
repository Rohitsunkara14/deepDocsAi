import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { Workspace } from "./Workspace";
import { api } from "../api/client";
import { document } from "../test/fixtures";
it("keeps uploaded documents in session state, selects them and supports All documents", async () => {
  vi.spyOn(api, "health").mockResolvedValue({
    status: "ok",
    service: "deepdocs-ai",
  });
  vi.spyOn(api, "upload").mockResolvedValue(document);
  const view = render(<Workspace />);
  await userEvent.upload(
    screen.getByLabelText("Choose document"),
    new File(["text"], "sample.txt", { type: "text/plain" }),
  );
  const docButton = await screen.findByRole("button", {
    name: /sample.txt 2 indexed chunks/,
  });
  expect(docButton).toHaveAttribute("aria-pressed", "true");
  expect(within(docButton).getByText(document.document_id)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /All documents/ }));
  expect(docButton).toHaveAttribute("aria-pressed", "false");
  view.unmount();
  render(<Workspace />);
  expect(
    screen.queryByRole("button", { name: /sample.txt 2 indexed chunks/ }),
  ).not.toBeInTheDocument();
});
