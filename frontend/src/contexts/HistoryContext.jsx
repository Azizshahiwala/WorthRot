import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useToast } from "./ToastContext.jsx";
import {
  HISTORY_STORAGE_KEY,
  isComparison,
  isGapCheck,
  isHistoryStorageAvailable,
  loadHistory,
  MAX_HISTORY_ENTRIES,
  saveHistory,
} from "../lib/historyStorage.js";

const HistoryContext = createContext(null);
const SAVED_VERDICTS = new Set(["Worth it", "Skim", "Rot", "Can't verify"]);
const HISTORY_SOURCES = new Set(["youtube", "transcript", "media", "compare"]);

function normalizeQuestion(question) {
  return question.trim().toLowerCase().replace(/\s+/g, " ");
}

function getEntrySource(entry) {
  if (HISTORY_SOURCES.has(entry.source)) return entry.source;
  return entry.url ? "youtube" : "transcript";
}

function comparisonKey(comparison) {
  return comparison.ranking
    .map((video) => video.videoId)
    .sort()
    .join(",");
}

function makeId() {
  try {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID();
    }
  } catch {
    // Fall through when the browser does not expose a usable UUID generator.
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

export function HistoryProvider({ children }) {
  const [entries, setEntries] = useState(loadHistory);
  const [available, setAvailable] = useState(isHistoryStorageAvailable);
  const { showToast } = useToast();

  const persist = useCallback(
    (nextEntries) => {
      const saved = saveHistory(nextEntries);
      const readable = saved.ok && isHistoryStorageAvailable();
      setEntries(readable ? loadHistory() : nextEntries);
      setAvailable(readable);
      if (!readable) {
        showToast(
          "History can’t be saved in this browser. Current results remain available until you leave.",
          "error",
        );
      }
      return readable;
    },
    [showToast],
  );

  const addEntry = useCallback(
    ({ question, videoId, url, result, source }) => {
      if (
        !question?.trim() ||
        !SAVED_VERDICTS.has(result?.verdict) ||
        (source === "compare" && !isComparison(result?.comparison))
      ) {
        return false;
      }
      const safeUrl = typeof url === "string" ? url : "";
      const entrySource = HISTORY_SOURCES.has(source)
        ? source
        : getEntrySource({ url: safeUrl });
      const normalizedQuestion = normalizeQuestion(question);
      const entry = {
        id: makeId(),
        createdAt: new Date().toISOString(),
        question: question.trim(),
        videoId: typeof videoId === "string" ? videoId : "",
        url: safeUrl,
        source: entrySource,
        verdict: result.verdict,
        facts: Array.isArray(result.facts)
          ? result.facts.map(({ text, timestamp, url: factUrl }) => ({
              text,
              timestamp: typeof timestamp === "string" ? timestamp : "",
              url: typeof factUrl === "string" ? factUrl : "",
            }))
          : [],
        missing: Array.isArray(result.missing) ? [...result.missing] : [],
      };
      if (isGapCheck(result.gap)) entry.gap = result.gap;
      if (entrySource === "compare" && isComparison(result.comparison)) {
        entry.comparison = result.comparison;
      }
      const nextEntries = [
        entry,
        ...entries.filter(
          (existing) => {
            const existingSource = getEntrySource(existing);
            if (entry.source === "media" || existingSource === "media") {
              return true;
            }
            if (entry.source === "compare" || existingSource === "compare") {
              return (
                entry.source !== existingSource ||
                normalizeQuestion(existing.question) !== normalizedQuestion ||
                !entry.comparison ||
                !existing.comparison ||
                comparisonKey(entry.comparison) !==
                  comparisonKey(existing.comparison)
              );
            }
            return (
              existing.videoId !== entry.videoId ||
              existingSource !== entry.source ||
              normalizeQuestion(existing.question) !== normalizedQuestion
            );
          },
        ),
      ].slice(0, MAX_HISTORY_ENTRIES);
      persist(nextEntries);
      return true;
    },
    [entries, persist],
  );

  const removeEntry = useCallback(
    (id) => {
      const nextEntries = entries.filter((entry) => entry.id !== id);
      if (nextEntries.length === entries.length) return false;
      persist(nextEntries);
      return true;
    },
    [entries, persist],
  );

  const clearHistory = useCallback(() => {
    const hadEntries = entries.length > 0;
    persist([]);
    return hadEntries;
  }, [entries, persist]);

  useEffect(() => {
    function syncHistory(event) {
      if (event.key !== null && event.key !== HISTORY_STORAGE_KEY) return;
      setEntries(loadHistory());
      setAvailable(isHistoryStorageAvailable());
    }

    window.addEventListener("storage", syncHistory);
    return () => window.removeEventListener("storage", syncHistory);
  }, []);

  const value = useMemo(
    () => ({
      entries,
      available,
      addEntry,
      removeEntry,
      clearHistory,
    }),
    [entries, available, addEntry, removeEntry, clearHistory],
  );

  return (
    <HistoryContext.Provider value={value}>{children}</HistoryContext.Provider>
  );
}

export function useHistory() {
  const context = useContext(HistoryContext);
  if (!context) {
    throw new Error("useHistory must be used within a HistoryProvider.");
  }
  return context;
}
