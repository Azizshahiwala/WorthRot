import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AnalysisProvider, useAnalysis } from "./AnalysisContext.jsx";
import { HistoryProvider, useHistory } from "./HistoryContext.jsx";
import { ToastProvider } from "./ToastContext.jsx";
import { RateLimitProvider } from "./RateLimitContext.jsx";
import { HISTORY_STORAGE_KEY, loadHistory } from "../lib/historyStorage.js";

let currentHistory;
let lastActionResult;
const originalFetch = globalThis.fetch;

function HistoryHarness() {
  currentHistory = useHistory();
  return (
    <div>
      <output data-testid="entries">
        {JSON.stringify(currentHistory.entries)}
      </output>
      <output data-testid="available">{String(currentHistory.available)}</output>
      <button
        onClick={() =>
          (lastActionResult = currentHistory.addEntry({
            question: "A separate question",
            videoId: "video-two",
            url: "https://youtu.be/video-two",
            result: {
              verdict: "Rot",
              facts: [],
              missing: ["not covered"],
            },
          }))
        }
      >
        Add other
      </button>
      <button
        onClick={() =>
          (lastActionResult = currentHistory.addEntry({
            question: "  How   does this work? ",
            videoId: "video-one",
            url: "https://youtu.be/video-one",
            result: {
              verdict: "Worth it",
              facts: [
                {
                  text: "It works",
                  timestamp: "00:10",
                  url: "https://youtu.be/video-one?t=10",
                  quote: "must not be stored",
                },
              ],
              missing: ["one gap"],
              meta: { tokens_in: 30, tokens_out: 4 },
            },
          }))
        }
      >
        Add first
      </button>
      <button
        onClick={() =>
          (lastActionResult = currentHistory.addEntry({
            question: "how does this work?",
            videoId: "video-one",
            url: "https://youtu.be/video-one",
            result: {
              verdict: "Skim",
              facts: [{ text: "New fact", timestamp: "00:20", url: "" }],
              missing: [],
            },
          }))
        }
      >
        Add duplicate
      </button>
      <button
        onClick={() =>
          (lastActionResult = currentHistory.removeEntry(
            currentHistory.entries[0]?.id,
          ))
        }
      >
        Remove
      </button>
      <button
        onClick={() =>
          (lastActionResult = currentHistory.clearHistory())
        }
      >
        Clear
      </button>
    </div>
  );
}

function renderHistory() {
  return render(
    <ToastProvider>
      <HistoryProvider>
        <HistoryHarness />
      </HistoryProvider>
    </ToastProvider>,
  );
}

function AnalysisHarness() {
  const { setQuestion, setUrl, analyze } = useAnalysis();
  useEffect(() => {
    setQuestion("Will this be saved?");
    setUrl("https://youtu.be/saved-video");
  }, [setQuestion, setUrl]);
  return (
    <button onClick={() => void analyze().catch(() => {})}>Analyze</button>
  );
}

function renderAnalysis() {
  return render(
    <ToastProvider>
      <HistoryProvider>
        <RateLimitProvider>
          <AnalysisProvider>
            <AnalysisHarness />
            <HistoryHarness />
          </AnalysisProvider>
        </RateLimitProvider>
      </HistoryProvider>
    </ToastProvider>,
  );
}

function entriesFromScreen() {
  return JSON.parse(screen.getByTestId("entries").textContent);
}

describe("HistoryContext", () => {
  beforeEach(() => {
    localStorage.clear();
    lastActionResult = undefined;
  });

  afterEach(() => {
    cleanup();
    globalThis.fetch = originalFetch;
  });

  it("throws a clear error if the hook is used outside its provider", () => {
    function OutsideProvider() {
      useHistory();
      return null;
    }

    expect(() => render(<OutsideProvider />)).toThrow(
      "useHistory must be used within a HistoryProvider.",
    );
  });

  it("deduplicates by video and normalized question and persists safe fields", () => {
    renderHistory();
    fireEvent.click(screen.getByText("Add first"));
    fireEvent.click(screen.getByText("Add other"));
    fireEvent.click(screen.getByText("Add duplicate"));

    const [entry, secondEntry] = entriesFromScreen();
    expect(entriesFromScreen()).toHaveLength(2);
    expect(secondEntry.videoId).toBe("video-two");
    expect(entry.question).toBe("how does this work?");
    expect(entry.verdict).toBe("Skim");
    expect(entry.facts[0].text).toBe("New fact");
    expect(entry).not.toHaveProperty("meta");
    expect(entry.facts[0]).not.toHaveProperty("quote");
    expect(loadHistory()).toEqual([entry, secondEntry]);
  });

  it("deduplicates legacy entries without a source field", () => {
    localStorage.setItem(
      HISTORY_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        entries: [
          {
            id: "legacy-entry",
            createdAt: "2026-11-05T00:00:00.000Z",
            question: "How does this work?",
            videoId: "video-one",
            url: "https://youtu.be/video-one",
            verdict: "Worth it",
            facts: [],
            missing: [],
          },
        ],
      }),
    );
    renderHistory();

    fireEvent.click(screen.getByText("Add duplicate"));

    expect(entriesFromScreen()).toHaveLength(1);
    expect(entriesFromScreen()[0].verdict).toBe("Skim");
    expect(entriesFromScreen()[0].source).toBe("youtube");
  });

  it("removes one item and reports clear results", () => {
    renderHistory();
    fireEvent.click(screen.getByText("Add first"));
    fireEvent.click(screen.getByText("Add duplicate"));
    act(() => {
      lastActionResult = currentHistory.removeEntry(entriesFromScreen()[0].id);
    });
    expect(lastActionResult).toBe(true);
    expect(entriesFromScreen()).toEqual([]);

    act(() => {
      lastActionResult = currentHistory.clearHistory();
    });
    expect(lastActionResult).toBe(false);
    fireEvent.click(screen.getByText("Add first"));
    act(() => {
      lastActionResult = currentHistory.clearHistory();
    });
    expect(lastActionResult).toBe(true);
    expect(entriesFromScreen()).toEqual([]);
    expect(JSON.parse(localStorage.getItem(HISTORY_STORAGE_KEY)).entries).toEqual(
      [],
    );
  });

  it("saves Can't verify results without metadata", () => {
    renderHistory();
    act(() => {
      lastActionResult = currentHistory.addEntry({
        question: "Question",
        videoId: "video",
        url: "",
        result: { verdict: "Can't verify", facts: [], missing: [] },
      });
    });
    expect(lastActionResult).toBe(true);
    expect(entriesFromScreen()).toHaveLength(1);
    expect(entriesFromScreen()[0].verdict).toBe("Can't verify");
  });

  it("automatically saves successful analyses without metadata", async () => {
    globalThis.fetch = async (url) => ({
      ok: true,
      headers: { get: () => null },
      json: async () => ({
        ...(url === "/limits"
          ? {
              limits: {
                analyze: { limit: 10, remaining: 10, resetsAt: "2026-11-06T00:00:00Z" },
                compare: { limit: 10, remaining: 10, resetsAt: "2026-11-06T00:00:00Z" },
                media: { limit: 10, remaining: 10, resetsAt: "2026-11-06T00:00:00Z" },
              },
            }
          : {
        verdict: "Skim",
        facts: [{ text: "A fact", timestamp: "00:12", url: "" }],
        missing: [],
        meta: {
          video_id: "saved-video",
          cached: false,
          tokens_in: 20,
          tokens_out: 5,
        },
            }),
      }),
    });
    renderAnalysis();

    await act(async () => {
      fireEvent.click(screen.getByText("Analyze"));
    });

    expect(loadHistory()).toHaveLength(1);
    expect(loadHistory()[0]).toMatchObject({
      question: "Will this be saved?",
      videoId: "saved-video",
      verdict: "Skim",
    });
    expect(loadHistory()[0]).not.toHaveProperty("meta");
  });

  it("does not save failed analyses", async () => {
    globalThis.fetch = async (url) => ({
      ok: false,
      headers: { get: () => null },
      json: async () =>
        url === "/limits"
          ? {
              limits: {
                analyze: { limit: 10, remaining: 10, resetsAt: "2026-11-06T00:00:00Z" },
                compare: { limit: 10, remaining: 10, resetsAt: "2026-11-06T00:00:00Z" },
                media: { limit: 10, remaining: 10, resetsAt: "2026-11-06T00:00:00Z" },
              },
            }
          : { message: "Analysis failed." },
    });
    renderAnalysis();

    await act(async () => {
      fireEvent.click(screen.getByText("Analyze"));
    });

    expect(loadHistory()).toEqual([]);
  });

  it("keeps in-memory history usable when storage writes are blocked", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    renderHistory();

    fireEvent.click(screen.getByText("Add first"));

    expect(entriesFromScreen()).toHaveLength(1);
    expect(screen.getByTestId("available").textContent).toBe("false");
  });

  it("refreshes entries when another tab changes browser storage", () => {
    renderHistory();
    localStorage.setItem(
      HISTORY_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        entries: [
          {
            id: "from-another-tab",
            createdAt: "2026-11-05T00:00:00.000Z",
            question: "Saved elsewhere",
            videoId: "video-two",
            url: "",
            verdict: "Rot",
            facts: [],
            missing: ["not covered"],
          },
        ],
      }),
    );

    act(() => {
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: HISTORY_STORAGE_KEY,
          newValue: localStorage.getItem(HISTORY_STORAGE_KEY),
        }),
      );
    });

    expect(entriesFromScreen()[0].question).toBe("Saved elsewhere");
  });
});
