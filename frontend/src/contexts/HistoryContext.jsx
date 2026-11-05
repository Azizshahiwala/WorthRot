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
  isHistoryStorageAvailable,
  loadHistory,
  MAX_HISTORY_ENTRIES,
  saveHistory,
} from "../lib/historyStorage.js";

const HistoryContext = createContext(null);
const SAVED_VERDICTS = new Set(["Worth it", "Skim", "Rot"]);

function normalizeQuestion(question) {
  return question.trim().toLowerCase().replace(/\s+/g, " ");
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
    ({ question, videoId, url, result }) => {
      if (!question?.trim() || !SAVED_VERDICTS.has(result?.verdict)) {
        return false;
      }
      const normalizedQuestion = normalizeQuestion(question);
      const entry = {
        id: makeId(),
        createdAt: new Date().toISOString(),
        question: question.trim(),
        videoId: typeof videoId === "string" ? videoId : "",
        url: typeof url === "string" ? url : "",
        verdict: result.verdict,
        facts: Array.isArray(result.facts)
          ? result.facts.map(({ text, timestamp, url: factUrl }) => ({
              text,
              timestamp,
              url: factUrl,
            }))
          : [],
        missing: Array.isArray(result.missing) ? [...result.missing] : [],
      };
      const nextEntries = [
        entry,
        ...entries.filter(
          (existing) =>
            existing.videoId !== entry.videoId ||
            normalizeQuestion(existing.question) !== normalizedQuestion,
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
