import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { compare as requestCompare } from "../api.js";
import { isValidYouTubeUrl } from "../lib/youtubeUrl.js";
import { useHistory } from "./HistoryContext.jsx";

const CompareContext = createContext(null);
const MAX_COMPARE_VIDEOS = 3;
const MIN_COMPARE_VIDEOS = 2;

export function CompareProvider({ children }) {
  const { addEntry } = useHistory();
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
      const response = await requestCompare({
        question: trimmedQuestion,
        urls: trimmedUrls,
      });
      response.ranking.forEach((video) => {
        if (!video.error && video.verdict !== "Can't verify") {
          addEntry({
            question: trimmedQuestion,
            videoId: video.videoId,
            url: video.url,
            result: video,
          });
        }
      });
      setResult(response);
      setStatus("success");
      return response;
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "The comparison request failed.";
      setError(message);
      setStatus("error");
      throw new Error(message);
    }
  }, [question, urls, addEntry]);

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
