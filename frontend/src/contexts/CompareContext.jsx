import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { compare as requestCompare } from "../api.js";
import { isValidYouTubeUrl } from "../lib/youtubeUrl.js";
import { useRateLimit } from "./RateLimitContext.jsx";

const CompareContext = createContext(null);
const MAX_COMPARE_VIDEOS = 3;
const MIN_COMPARE_VIDEOS = 2;

export function CompareProvider({ children }) {
  const { update: updateRateLimit } = useRateLimit();
  const [question, setQuestion] = useState("");
  const [urls, setUrls] = useState(["", ""]);
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const setUrl = useCallback((index, value) => {
    setUrls((current) =>
      current.map((url, currentIndex) =>
        currentIndex === index ? value : url,
      ),
    );
  }, []);

  const addUrl = useCallback(() => {
    setUrls((current) =>
      current.length < MAX_COMPARE_VIDEOS ? [...current, ""] : current,
    );
  }, []);

  const removeUrl = useCallback((index) => {
    setUrls((current) =>
      current.length > MIN_COMPARE_VIDEOS
        ? current.filter((_, currentIndex) => currentIndex !== index)
        : current,
    );
  }, []);

  const compare = useCallback(async () => {
    const trimmedQuestion = question.trim();
    const trimmedUrls = urls.map((url) => url.trim());
    const validationMessage = !trimmedQuestion
      ? "Add a question to continue."
      : trimmedUrls.length < MIN_COMPARE_VIDEOS ||
          trimmedUrls.length > MAX_COMPARE_VIDEOS
        ? "Compare 2 to 3 YouTube videos."
        : trimmedUrls.some((url) => !isValidYouTubeUrl(url))
          ? "Enter valid YouTube video URLs."
          : "";

    if (validationMessage) {
      setResult(null);
      setError(validationMessage);
      setStatus("error");
      throw new Error(validationMessage);
    }

    setStatus("loading");
    setResult(null);
    setError("");
    try {
      const { result: response, rate } = await requestCompare({
        question: trimmedQuestion,
        urls: trimmedUrls,
      });
      updateRateLimit("compare", rate);
      setResult(response);
      setStatus("success");
      return response;
    } catch (requestError) {
      updateRateLimit(
        "compare",
        requestError?.status === 429
          ? { ...(requestError.rate || {}), remaining: 0 }
          : requestError?.rate,
      );
      const message =
        requestError instanceof Error
          ? requestError.message
          : "The comparison request failed.";
      setError(message);
      setStatus("error");
      throw new Error(message);
    }
  }, [question, urls, updateRateLimit]);

  const reset = useCallback(() => {
    setQuestion("");
    setUrls(["", ""]);
    setStatus("idle");
    setResult(null);
    setError("");
  }, []);

  const value = useMemo(
    () => ({
      question,
      urls,
      status,
      result,
      error,
      setQuestion,
      setUrl,
      addUrl,
      removeUrl,
      compare,
      reset,
    }),
    [
      question,
      urls,
      status,
      result,
      error,
      setUrl,
      addUrl,
      removeUrl,
      compare,
      reset,
    ],
  );

  return (
    <CompareContext.Provider value={value}>{children}</CompareContext.Provider>
  );
}

export function useCompare() {
  const context = useContext(CompareContext);
  if (!context) {
    throw new Error("useCompare must be used within a CompareProvider.");
  }
  return context;
}
