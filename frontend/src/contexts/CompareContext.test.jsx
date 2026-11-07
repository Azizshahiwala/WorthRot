import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompareProvider, useCompare } from "./CompareContext.jsx";
import { RateLimitProvider } from "./RateLimitContext.jsx";
import { HistoryProvider } from "./HistoryContext.jsx";
import { ToastProvider } from "./ToastContext.jsx";

vi.mock("../api.js", () => ({
  compare: vi.fn(),
  getRateLimits: vi.fn().mockResolvedValue({
    analyze: { limit: 10, remaining: 10, resetsAt: "2026-11-06T00:00:00Z" },
    compare: { limit: 10, remaining: 10, resetsAt: "2026-11-06T00:00:00Z" },
    media: { limit: 10, remaining: 10, resetsAt: "2026-11-06T00:00:00Z" },
  }),
}));
import { compare as requestCompare } from "../api.js";

function CompareHarness() {
  const { urls, setUrl, addUrl, removeUrl, setQuestion, compare, result } =
    useCompare();
  return (
    <div>
      <output data-testid="urls">{JSON.stringify(urls)}</output>
      <output data-testid="result">{JSON.stringify(result)}</output>
      <button onClick={addUrl}>Add URL</button>
      <button onClick={() => removeUrl(0)}>Remove first</button>
      <button onClick={() => setUrl(0, "https://youtu.be/abcdefghijk")}>
        Set first
      </button>
      <button onClick={() => setUrl(1, "https://youtu.be/lmnopqrstuv")}>
        Set second
      </button>
      <button onClick={() => setQuestion("How does this work?")}>
        Set question
      </button>
      <button onClick={() => void compare().catch(() => {})}>Compare</button>
    </div>
  );
}

function renderCompare() {
  return render(
    <ToastProvider>
      <HistoryProvider>
        <RateLimitProvider>
          <CompareProvider>
            <CompareHarness />
          </CompareProvider>
        </RateLimitProvider>
      </HistoryProvider>
    </ToastProvider>,
  );
}

describe("CompareContext", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(cleanup);

  it("throws if used outside its provider", () => {
    function OutsideProvider() {
      useCompare();
      return null;
    }

    expect(() => render(<OutsideProvider />)).toThrow(
      "useCompare must be used within a CompareProvider.",
    );
  });

  it("enforces the two-to-three URL bounds", () => {
    renderCompare();

    expect(JSON.parse(screen.getByTestId("urls").textContent)).toHaveLength(2);
    fireEvent.click(screen.getByText("Remove first"));
    expect(JSON.parse(screen.getByTestId("urls").textContent)).toHaveLength(2);

    fireEvent.click(screen.getByText("Add URL"));
    fireEvent.click(screen.getByText("Add URL"));
    expect(JSON.parse(screen.getByTestId("urls").textContent)).toHaveLength(3);

    fireEvent.click(screen.getByText("Remove first"));
    expect(JSON.parse(screen.getByTestId("urls").textContent)).toHaveLength(2);
  });

  it("updates a URL at its selected index", () => {
    renderCompare();
    fireEvent.click(screen.getByText("Set first"));

    expect(JSON.parse(screen.getByTestId("urls").textContent)[0]).toBe(
      "https://youtu.be/abcdefghijk",
    );
  });

  it("saves the ranked results and agreement to History", async () => {
    requestCompare.mockResolvedValue({
      rate: null,
      result: {
      question: "How does this work?",
      best: "abcdefghijk",
      ranking: [
        {
          rank: 1,
          videoId: "abcdefghijk",
          url: "https://youtu.be/abcdefghijk",
          verdict: "Worth it",
          facts: [{ text: "Verified", timestamp: "00:12", url: "https://youtu.be/abcdefghijk?t=12" }],
          missing: [],
          error: null,
          meta: { cached: false, tokens_in: 20, tokens_out: 5 },
        },
        {
          rank: 2,
          videoId: "lmnopqrstuv",
          url: "https://youtu.be/lmnopqrstuv",
          verdict: "Can't verify",
          facts: [],
          missing: [],
          error: { message: "Could not check" },
          meta: { cached: false, tokens_in: 0, tokens_out: 0 },
        },
      ],
      agreement: null,
      meta: { tokens_in_total: 20, tokens_out_total: 5 },
      },
    });

    renderCompare();
    fireEvent.click(screen.getByText("Set first"));
    fireEvent.click(screen.getByText("Set second"));
    fireEvent.click(screen.getByText("Set question"));
    fireEvent.click(screen.getByText("Compare"));

    expect((await screen.findByTestId("result")).textContent).toContain(
      '"question":"How does this work?"',
    );
    const history = JSON.parse(
      localStorage.getItem("worthrot:history:v1"),
    ).entries;
    expect(history).toHaveLength(1);
    expect(history[0]).toMatchObject({
      source: "compare",
      question: "How does this work?",
      comparison: {
        best: "abcdefghijk",
        agreement: null,
        ranking: [{ videoId: "abcdefghijk" }, { videoId: "lmnopqrstuv" }],
      },
    });
  });
});
