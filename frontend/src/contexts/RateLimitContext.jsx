import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { getRateLimits } from "../api.js";

const RateLimitContext = createContext(null);
const FEATURES = ["analyze", "compare", "media"];

export function RateLimitProvider({ children }) {
  const [limits, setLimits] = useState({
    analyze: null,
    compare: null,
    media: null,
  });
  const [error, setError] = useState("");
  const requested = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const currentLimits = await getRateLimits();
      setLimits(currentLimits);
      setError("");
      return currentLimits;
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Daily request limits could not be loaded.",
      );
      throw requestError;
    }
  }, []);

  const update = useCallback((feature, rate) => {
    if (!FEATURES.includes(feature) || !rate) return;
    setLimits((current) => ({
      ...current,
      [feature]: {
        ...(current[feature] || {}),
        ...rate,
      },
    }));
  }, []);

  useEffect(() => {
    if (requested.current) return;
    requested.current = true;
    refresh().catch(() => {});
  }, [refresh]);

  const value = useMemo(
    () => ({ limits, refresh, update, error }),
    [limits, refresh, update, error],
  );

  return (
    <RateLimitContext.Provider value={value}>
      {children}
    </RateLimitContext.Provider>
  );
}

export function useRateLimit() {
  const context = useContext(RateLimitContext);
  if (!context) {
    throw new Error("useRateLimit must be used within a RateLimitProvider.");
  }
  return context;
}
