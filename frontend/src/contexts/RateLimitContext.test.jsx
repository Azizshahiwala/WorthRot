import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import RateLimitNotice from "../components/RateLimitNotice.jsx";
import {
  RateLimitProvider,
  useRateLimit,
} from "./RateLimitContext.jsx";

vi.mock("../api.js", () => ({
  getRateLimits: vi.fn(),
}));
import { getRateLimits } from "../api.js";

const rates = {
  analyze: { limit: 10, remaining: 7, resetsAt: "2026-11-06T00:00:00Z" },
  compare: { limit: 10, remaining: 10, resetsAt: "2026-11-06T00:00:00Z" },
  media: { limit: 10, remaining: 10, resetsAt: "2026-11-06T00:00:00Z" },
};

function renderNotice() {
  return render(
    <RateLimitProvider>
      <RateLimitNotice feature="analyze" />
    </RateLimitProvider>,
  );
}

describe("RateLimitContext", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(cleanup);

  it("throws if the hook is used outside the provider", () => {
    function OutsideProvider() {
      useRateLimit();
      return null;
    }

    expect(() => render(<OutsideProvider />)).toThrow(
      "useRateLimit must be used within a RateLimitProvider.",
    );
  });

  it("shows a known remaining count", async () => {
    getRateLimits.mockResolvedValue(rates);
    renderNotice();

    expect((await screen.findByRole("status")).textContent).toContain(
      "7 of 10 left today",
    );
  });

  it("shows the local reset time when the quota is exhausted", async () => {
    getRateLimits.mockResolvedValue({
      ...rates,
      analyze: { ...rates.analyze, remaining: 0 },
    });
    renderNotice();

    expect((await screen.findByRole("status")).textContent).toMatch(
      /^Daily limit reached\. Resets at /,
    );
  });

  it("shows an unknown state while limits are loading", () => {
    getRateLimits.mockImplementation(() => new Promise(() => {}));
    renderNotice();

    expect(screen.getByRole("status").textContent).toContain(
      "Checking daily limit…",
    );
  });
});
