import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { AnswerPanel } from "./AnswerPanel";
import { answer } from "../test/fixtures";
it("renders citations with original chunk index and highlights the referenced card", async () => {
  render(<AnswerPanel answer={answer} loading={false} />);
  expect(screen.getByText(/Page not available \(TXT\)/)).toHaveTextContent(
    "Chunk 0",
  );
  await userEvent.click(screen.getByRole("button", { name: "Show source 1" }));
  expect(document.getElementById("source-1")).toHaveClass("active");
  expect(document.getElementById("source-1")).toHaveFocus();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});
it("preserves unknown markers as text and renders safe markdown, not raw HTML or remote images", () => {
  render(
    <AnswerPanel
      answer={{
        ...answer,
        answer:
          "**Verified** [1]. Unknown [99]. <script>alert(1)</script> ![external](https://example.com/pixel)",
      }}
      loading={false}
    />,
  );
  expect(screen.getByText("Verified").tagName).toBe("STRONG");
  expect(screen.getAllByRole("button")).toHaveLength(1);
  expect(document.querySelector("script")).toBeNull();
  expect(document.querySelector("img")).toBeNull();
  expect(screen.getByText(/Unknown \[99\]/)).toBeInTheDocument();
});
it("handles no-answer responses without fake citations", () => {
  render(
    <AnswerPanel
      answer={{
        ...answer,
        answer: "The documents do not contain enough evidence.",
        citations: [],
      }}
      loading={false}
    />,
  );
  expect(
    screen.getByText("No citations returned for this answer"),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
