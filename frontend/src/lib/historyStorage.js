export const HISTORY_STORAGE_KEY = "worthrot:history:v1";
export const MAX_HISTORY_ENTRIES = 50;
const HISTORY_VERSION = 1;
const VERDICTS = new Set(["Worth it", "Skim", "Rot"]);

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isSafeUrl(value) {
  if (value === "") return true;
  try {
    return ["http:", "https:"].includes(new URL(value).protocol);
  } catch {
    return false;
  }
}

function getStorage() {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage;
  } catch {
    return null;
  }
}

export function isHistoryStorageAvailable() {
  const storage = getStorage();
  if (!storage) return false;
  try {
    storage.getItem(HISTORY_STORAGE_KEY);
    return true;
  } catch {
    return false;
  }
}

export function validateEntry(entry) {
  if (
    !isRecord(entry) ||
    typeof entry.id !== "string" ||
    !entry.id ||
    typeof entry.createdAt !== "string" ||
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(
      entry.createdAt,
    ) ||
    !Number.isFinite(Date.parse(entry.createdAt)) ||
    typeof entry.question !== "string" ||
    !entry.question.trim() ||
    typeof entry.videoId !== "string" ||
    typeof entry.url !== "string" ||
    !isSafeUrl(entry.url) ||
    !VERDICTS.has(entry.verdict) ||
    !Array.isArray(entry.facts) ||
    !entry.facts.every(
      (fact) =>
        isRecord(fact) &&
        typeof fact.text === "string" &&
        typeof fact.timestamp === "string" &&
        typeof fact.url === "string" &&
        isSafeUrl(fact.url),
    ) ||
    !Array.isArray(entry.missing) ||
    !entry.missing.every((item) => typeof item === "string")
  ) {
    return false;
  }
  return true;
}

function sanitizeEntry(entry) {
  return {
    id: entry.id,
    createdAt: entry.createdAt,
    question: entry.question,
    videoId: entry.videoId,
    url: entry.url,
    verdict: entry.verdict,
    facts: entry.facts.map(({ text, timestamp, url }) => ({
      text,
      timestamp,
      url,
    })),
    missing: [...entry.missing],
  };
}

export function migrate(envelope) {
  if (!isRecord(envelope)) return null;
  if (envelope.version === HISTORY_VERSION) return envelope;
  if (Number.isInteger(envelope.version) && envelope.version < HISTORY_VERSION) {
    return { version: HISTORY_VERSION, entries: [] };
  }
  return null;
}

export function loadHistory() {
  const storage = getStorage();
  if (!storage) return [];

  try {
    const stored = storage.getItem(HISTORY_STORAGE_KEY);
    if (!stored) return [];
    const envelope = JSON.parse(stored);
    const migrated = migrate(envelope);
    if (!migrated || !Array.isArray(migrated.entries)) return [];
    return migrated.entries
      .filter(validateEntry)
      .slice(0, MAX_HISTORY_ENTRIES)
      .map(sanitizeEntry);
  } catch {
    return [];
  }
}

function isQuotaExceeded(error) {
  return (
    error?.name === "QuotaExceededError" ||
    error?.code === 22 ||
    error?.code === 1014
  );
}

function writeHistory(storage, entries) {
  storage.setItem(
    HISTORY_STORAGE_KEY,
    JSON.stringify({ version: HISTORY_VERSION, entries }),
  );
}

export function saveHistory(entries) {
  const storage = getStorage();
  if (!storage) return { ok: false, reason: "unavailable" };

  const validEntries = Array.isArray(entries)
    ? entries.filter(validateEntry).slice(0, MAX_HISTORY_ENTRIES).map(sanitizeEntry)
    : [];
  try {
    writeHistory(storage, validEntries);
    return { ok: true };
  } catch (error) {
    if (!isQuotaExceeded(error)) return { ok: false, reason: "unavailable" };

    try {
      writeHistory(storage, validEntries.slice(0, -1));
      return { ok: true };
    } catch {
      return { ok: false, reason: "quota" };
    }
  }
}
