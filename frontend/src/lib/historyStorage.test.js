import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  HISTORY_STORAGE_KEY,
  isHistoryStorageAvailable,
  loadHistory,
  MAX_HISTORY_ENTRIES,
  saveHistory,
  validateEntry,
} from "./historyStorage.js";

function makeEntry(id) {
  return {
    id,
    createdAt: "2026-11-05T00:00:00.000Z",
    question: `Question ${id}`,
    videoId: `video-${id}`,
    url: `https://youtu.be/${id}`,
    verdict: "Worth it",
    facts: [{ text: "A verified fact", timestamp: "00:12", url: "" }],
    missing: [],
  };
}

describe("historyStorage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("returns an empty list for missing, corrupt, and invalid envelopes", () => {
    expect(loadHistory()).toEqual([]);
    localStorage.setItem(HISTORY_STORAGE_KEY, "{broken");
    expect(loadHistory()).toEqual([]);
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify({ version: 1 }));
    expect(loadHistory()).toEqual([]);
    localStorage.setItem(
      HISTORY_STORAGE_KEY,
      JSON.stringify({ version: 2, entries: [makeEntry("a")] }),
    );
    expect(loadHistory()).toEqual([]);
  });

  it("drops invalid entries and only loads the safe entry fields", () => {
    const entry = {
      ...makeEntry("valid"),
      transcript: "must not be retained",
      meta: { tokens_in: 100 },
    };
    localStorage.setItem(
      HISTORY_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        entries: [entry, { ...makeEntry("invalid"), facts: [null] }],
      }),
    );

    expect(loadHistory()).toEqual([makeEntry("valid")]);
  });

  it("validates the full entry shape", () => {
    expect(validateEntry(makeEntry("valid"))).toBe(true);
    expect(
      validateEntry({ ...makeEntry("unverified"), verdict: "Can't verify" }),
    ).toBe(true);
    expect(validateEntry({ ...makeEntry("bad"), source: "unknown" })).toBe(false);
    expect(validateEntry({ ...makeEntry("bad"), createdAt: "not a date" })).toBe(
      false,
    );
  });

  it("saves the versioned envelope", () => {
    const entries = [makeEntry("one")];

    expect(saveHistory(entries)).toEqual({ ok: true });
    expect(JSON.parse(localStorage.getItem(HISTORY_STORAGE_KEY))).toEqual({
      version: 1,
      entries,
    });
  });

  it("caps saved and loaded entries at the maximum", () => {
    const entries = Array.from({ length: MAX_HISTORY_ENTRIES + 1 }, (_, index) =>
      makeEntry(String(index)),
    );
    expect(saveHistory(entries)).toEqual({ ok: true });
    expect(loadHistory()).toHaveLength(MAX_HISTORY_ENTRIES);
    expect(loadHistory()[0].id).toBe("0");
  });

  it("drops the oldest entry and retries once on quota errors", () => {
    const originalSetItem = Storage.prototype.setItem;
    let firstWrite = true;
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (
      key,
      value,
    ) {
      if (firstWrite) {
        firstWrite = false;
        const error = new Error("storage full");
        error.name = "QuotaExceededError";
        throw error;
      }
      return originalSetItem.call(this, key, value);
    });

    expect(saveHistory([makeEntry("new"), makeEntry("old")])).toEqual({
      ok: true,
    });
    expect(loadHistory().map((entry) => entry.id)).toEqual(["new"]);
  });

  it("reports failure when localStorage is blocked", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(saveHistory([makeEntry("one")])).toEqual({
      ok: false,
      reason: "unavailable",
    });
    expect(loadHistory()).toEqual([]);
  });

  it("reports quota failure when the retry also fails", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      const error = new Error("storage full");
      error.name = "QuotaExceededError";
      throw error;
    });

    expect(saveHistory([makeEntry("one")])).toEqual({
      ok: false,
      reason: "quota",
    });
  });

  it("detects blocked reads without throwing", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(isHistoryStorageAvailable()).toBe(false);
    expect(loadHistory()).toEqual([]);
  });
});
