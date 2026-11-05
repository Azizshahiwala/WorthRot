import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { useEffect } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { loadHistory } from "../lib/historyStorage.js";
import { HistoryProvider } from "./HistoryContext.jsx";
import { ToastProvider } from "./ToastContext.jsx";
import { useOther } from "./OtherContext.jsx";
import { OtherProvider } from "./OtherContext.jsx";

describe("OtherContext", () => {
  afterEach(() => {
    cleanup();
    globalThis.fetch = originalFetch;
    localStorage.clear();
  });

  const originalFetch = globalThis.fetch;

  it("throws if used outside its provider", () => {
    function OutsideProvider() {
      useOther();
      return null;
    }
    expect(() => render(<OutsideProvider />)).toThrow(
      "useOther must be used within an OtherProvider.",
    );
  });

  it("saves successful media results in history without storing the upload", async () => {
    localStorage.clear();
    globalThis.fetch = async () => ({
      ok: true,
      json: async () => ({
        verdict: "Can't verify",
        source: "frames",
        facts: [{ text: "A frame fact", timestamp: null, url: null }],
        missing: ["speech not available"],
        meta: { tokens_in: 0, tokens_out: 0, frames_sent: 2 },
      }),
    });

    function OtherHarness() {
      const { setQuestion, setFile, analyze, file } = useOther();
      useEffect(() => {
        setQuestion("What is in this clip?");
        setFile(new File(["audio"], "private-upload.mp3", { type: "audio/mpeg" }));
      }, [setFile, setQuestion]);
      return (
        <button onClick={() => void analyze().catch(() => {})}>
          Analyze {file ? "ready" : "loading"}
        </button>
      );
    }

    render(
      <ToastProvider>
        <HistoryProvider>
          <OtherProvider>
            <OtherHarness />
          </OtherProvider>
        </HistoryProvider>
      </ToastProvider>,
    );

    await act(async () => {
      fireEvent.click(await screen.findByText("Analyze ready"));
    });

    await waitFor(() => expect(loadHistory()).toHaveLength(1));
    expect(loadHistory()[0]).toMatchObject({
      question: "What is in this clip?",
      source: "media",
      videoId: "",
      url: "",
      verdict: "Can't verify",
      facts: [{ text: "A frame fact", timestamp: "", url: "" }],
      missing: ["speech not available"],
    });
    expect(JSON.stringify(loadHistory())).not.toContain("private-upload.mp3");
  });
});
