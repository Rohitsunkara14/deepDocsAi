import { expect, it } from "vitest";
import { apiBaseUrl } from "./config";
it("has no implicit localhost backend in production", () =>
  expect(apiBaseUrl(undefined, false)).toBe(""));
it("preserves explicit hosted API configuration", () =>
  expect(apiBaseUrl("https://api.example.com", false)).toBe(
    "https://api.example.com",
  ));
it("keeps the local development default", () =>
  expect(apiBaseUrl(undefined, true)).toBe("http://localhost:8000"));
