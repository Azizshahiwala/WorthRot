import { afterEach, describe, expect, it, vi } from "vitest";
import { analyzeMedia, compare, parseRateLimitHeaders } from "./api.js";

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

    const response = await analyzeMedia(formData);
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe("/analyze-media");
    expect(options.method).toBe("POST");
    expect(options.body).toBe(formData);
    expect(options.headers).toBeUndefined();
    expect(response.result.verdict).toBe("Can't verify");
    expect(response.rate).toBeNull();
  });
});

describe("compare", () => {
  it("accepts nullable agreement and optional gap fields", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          question: "Question?",
          best: null,
          ranking: [],
          agreement: null,
          meta: { tokens_in_total: 0, tokens_out_total: 0 },
        }),
      }),
    );

    await expect(compare({ question: "Question?", urls: [] })).resolves.toMatchObject({
      result: { agreement: null },
      rate: null,
    });
  });
});

describe("parseRateLimitHeaders", () => {
  it("parses limit, remaining count, and reset time", () => {
    const headers = new Headers({
      "X-RateLimit-Limit": "10",
      "X-RateLimit-Remaining": "7",
      "X-RateLimit-Reset": "1793923200",
    });

    expect(parseRateLimitHeaders(headers)).toEqual({
      limit: 10,
      remaining: 7,
      resetsAt: new Date(1793923200 * 1000).toISOString(),
    });
  });

  it("returns null when the response has no valid rate headers", () => {
    expect(parseRateLimitHeaders(new Headers())).toBeNull();
  });
});
