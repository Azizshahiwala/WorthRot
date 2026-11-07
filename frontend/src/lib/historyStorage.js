export const HISTORY_STORAGE_KEY = "worthrot:history:v1";
export const MAX_HISTORY_ENTRIES = 50;
const HISTORY_VERSION = 1;
const VERDICTS = new Set(["Worth it", "Skim", "Rot", "Can't verify"]);
const HISTORY_SOURCES = new Set(["youtube", "transcript", "media", "compare"]);
const GAP_STATUSES = new Set(["covered", "partial", "missing"]);
const GAP_LABELS = new Set(["All covered", "Partly covered", "Not covered"]);

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

export function isGapCheck(value) {
  return (
    isRecord(value) &&
    Number.isInteger(value.covered) &&
    Number.isInteger(value.total) &&
    value.covered >= 0 &&
    value.covered <= value.total &&
    value.total >= 0 &&
    value.total <= 4 &&
    GAP_LABELS.has(value.label) &&
    Array.isArray(value.parts) &&
    value.parts.length === value.total &&
    value.parts.every(
      (part) =>
        isRecord(part) &&
        typeof part.text === "string" &&
        GAP_STATUSES.has(part.status),
    )
  );
}

function isAgreement(value, ranking) {
  if (!isRecord(value)) return false;
  const labels = new Set(
    ranking.filter((video) => video.facts.length).map((video) =>
      String.fromCharCode(64 + video.rank),
    ),
  );
  return (
    Array.isArray(value.agree) &&
    value.agree.every(
      (item) =>
        isRecord(item) &&
        typeof item.point === "string" &&
        Array.isArray(item.videos) &&
        item.videos.length >= 2 &&
        item.videos.every((label) => labels.has(label)),
    ) &&
    Array.isArray(value.disagree) &&
    value.disagree.every(
      (item) =>
        isRecord(item) &&
        typeof item.point === "string" &&
        Array.isArray(item.positions) &&
        item.positions.length >= 2 &&
        item.positions.every(
          (position) =>
            isRecord(position) &&
            labels.has(position.video) &&
            typeof position.claim === "string",
        ),
    ) &&
    Array.isArray(value.unanswered) &&
    value.unanswered.every((item) => typeof item === "string")
  );
}

export function isComparison(value) {
  if (
    !isRecord(value) ||
    (typeof value.best !== "string" && value.best !== null) ||
    !Array.isArray(value.ranking) ||
    value.ranking.length < 2 ||
    value.ranking.length > 3
  ) {
    return false;
  }
  const rankingIsValid = value.ranking.every(
    (video, index) =>
      isRecord(video) &&
      video.rank === index + 1 &&
      typeof video.videoId === "string" &&
      typeof video.url === "string" &&
      isSafeUrl(video.url) &&
      VERDICTS.has(video.verdict) &&
      Array.isArray(video.facts) &&
      video.facts.length <= 5 &&
      video.facts.every(
        (fact) =>
          isRecord(fact) &&
          typeof fact.text === "string" &&
          typeof fact.timestamp === "string" &&
          typeof fact.url === "string" &&
          isSafeUrl(fact.url),
      ) &&
      Array.isArray(video.missing) &&
      video.missing.every((item) => typeof item === "string") &&
      (video.error === null ||
        (isRecord(video.error) && typeof video.error.message === "string")) &&
      (video.gap === undefined || video.gap === null || isGapCheck(video.gap)),
  );
  return (
    rankingIsValid &&
    (value.agreement === null || isAgreement(value.agreement, value.ranking))
  );
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
    (entry.source !== undefined && !HISTORY_SOURCES.has(entry.source)) ||
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
    !entry.missing.every((item) => typeof item === "string") ||
    (entry.gap !== undefined && entry.gap !== null && !isGapCheck(entry.gap)) ||
    (entry.source === "compare" && !isComparison(entry.comparison)) ||
    (entry.source !== "compare" && entry.comparison !== undefined)
  ) {
    return false;
  }
  return true;
}

function sanitizeEntry(entry) {
  const sanitized = {
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
  if (HISTORY_SOURCES.has(entry.source)) {
    sanitized.source = entry.source;
  }
  if (isGapCheck(entry.gap)) sanitized.gap = entry.gap;
  if (entry.source === "compare") {
    sanitized.comparison = {
      best: entry.comparison.best,
      ranking: entry.comparison.ranking.map((video) => ({
        rank: video.rank,
        videoId: video.videoId,
        url: video.url,
        verdict: video.verdict,
        facts: video.facts.map(({ text, timestamp, url }) => ({
          text,
          timestamp,
          url,
        })),
        missing: [...video.missing],
        error: video.error,
        ...(isGapCheck(video.gap) ? { gap: video.gap } : {}),
      })),
      agreement: entry.comparison.agreement,
    };
  }
  return sanitized;
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
