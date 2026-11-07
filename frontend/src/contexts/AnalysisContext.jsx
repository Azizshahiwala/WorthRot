import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { analyzeVideo } from "../api.js";
import { useHistory } from "./HistoryContext.jsx";
import { useRateLimit } from "./RateLimitContext.jsx";

const AnalysisContext = createContext(null);

export function AnalysisProvider({ children }) {
  const { addEntry } = useHistory();
  const { update: updateRateLimit } = useRateLimit();
  const [question, setQuestion] = useState("");
  const [url, setUrl] = useState("");
  const [transcript, setTranscript] = useState("");
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const analyze = useCallback(async () => {
    const validationMessage = !question.trim()
      ? "Add a question to continue."
      : !url.trim() && !transcript.trim()
        ? "Add a YouTube URL or paste a transcript to continue."
        : "";
    if (validationMessage) {
      const validationError = new Error(validationMessage);
      setResult(null);
      setError(validationMessage);
      setStatus("error");
      throw validationError;
    }

    setStatus("loading");
    setResult(null);
    setError("");

    try {
      const { result: response, rate } = await analyzeVideo({
        question,
        url,
        transcript,
      });
      updateRateLimit("analyze", rate);
      addEntry({
        question,
        url: url.trim(),
        videoId: response.meta.video_id,
        source: url.trim() ? "youtube" : "transcript",
        result: response,
      });
      setResult({
        verdict: response.verdict,
        facts: response.facts,
        missing: response.missing,
        gap: response.gap,
        meta: response.meta,
      });
      setStatus("success");
      return response;
    } catch (requestError) {
      updateRateLimit(
        "analyze",
        requestError?.status === 429
          ? { ...(requestError.rate || {}), remaining: 0 }
          : requestError?.rate,
      );
      const message =
        requestError instanceof Error
          ? requestError.message
          : "The analysis request failed.";
      const failedResult = requestError?.analysisResult;
      setResult(
        failedResult
          ? {
              verdict: failedResult.verdict,
              facts: failedResult.facts,
              missing: failedResult.missing,
              gap: failedResult.gap,
              meta: failedResult.meta,
            }
          : null,
      );
      setError(message);
      setStatus("error");
      throw new Error(message);
    }
  }, [question, url, transcript, addEntry, updateRateLimit]);

  const reset = useCallback(() => {
    setQuestion("");
    setUrl("");
    setTranscript("");
    setStatus("idle");
    setResult(null);
    setError("");
  }, []);

  const value = useMemo(
    () => ({
      question,
      setQuestion,
      url,
      setUrl,
      transcript,
      setTranscript,
      status,
      result,
      error,
      analyze,
      reset,
    }),
    [
      question,
      url,
      transcript,
      status,
      result,
      error,
      analyze,
      reset,
    ],
  );

  return (
    <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>
  );
}

export function useAnalysis() {
  const context = useContext(AnalysisContext);
  if (!context) {
    throw new Error("useAnalysis must be used within an AnalysisProvider.");
  }
  return context;
}
