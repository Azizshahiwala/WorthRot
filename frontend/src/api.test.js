import { afterEach, describe, expect, it, vi } from "vitest";
import { analyzeMedia } from "./api.js";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("analyzeMedia", () => {
  it("sends multipart data without setting a content type", async () => {
    const formData = new FormData();
    formData.set("question", "What is shown?");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          verdict: "Can't verify",
          source: "speech",
          facts: [],
          missing: ["No transcript available."],
          meta: { tokens_in: 0, tokens_out: 0, frames_sent: 0 },
        }),
      }),
    );

    await analyzeMedia(formData);
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe("/analyze-media");
    expect(options.method).toBe("POST");
    expect(options.body).toBe(formData);
    expect(options.headers).toBeUndefined();
  });
});
