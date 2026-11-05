import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { analyzeMedia as requestMediaAnalysis } from "../api.js";
import { validateMediaFile } from "../lib/mediaFile.js";
import { useHistory } from "./HistoryContext.jsx";

const OtherContext = createContext(null);

export function OtherProvider({ children }) {
  const { addEntry } = useHistory();
  const [question, setQuestion] = useState("");
  const [file, setSelectedFile] = useState(null);
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [fileInputVersion, setFileInputVersion] = useState(0);

  const setFile = useCallback((nextFile) => {
    if (!nextFile) {
      setSelectedFile(null);
      setFileInputVersion((version) => version + 1);
      setStatus("idle");
      setResult(null);
      setError("");
      return "";
    }
    const validationError = validateMediaFile(nextFile);
    setSelectedFile(validationError ? null : nextFile);
    if (validationError) {
      setFileInputVersion((version) => version + 1);
    }
    setResult(null);
    setError(validationError);
    setStatus(validationError ? "error" : "idle");
    return validationError;
  }, []);

  const analyze = useCallback(async () => {
    const validationError =
      !question.trim()
        ? "Add a question to continue."
        : validateMediaFile(file);
    if (validationError) {
      setResult(null);
      setError(validationError);
      setStatus("error");
      throw new Error(validationError);
    }

    const formData = new FormData();
    formData.set("question", question.trim());
    formData.set("file", file);
    setStatus("loading");
    setResult(null);
    setError("");
    try {
      const response = await requestMediaAnalysis(formData);
      addEntry({
        question: question.trim(),
        videoId: "",
        url: "",
        source: "media",
        result: response,
      });
      setResult(response);
      setStatus("success");
      return response;
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "The media request failed.";
      setError(message);
      setStatus("error");
      throw new Error(message);
    }
  }, [addEntry, file, question]);

  const reset = useCallback(() => {
    setQuestion("");
    setSelectedFile(null);
    setFileInputVersion((version) => version + 1);
    setStatus("idle");
    setResult(null);
    setError("");
  }, []);

  const value = useMemo(
    () => ({
      question,
      file,
      fileInputVersion,
      status,
      result,
      error,
      setQuestion,
      setFile,
      analyze,
      reset,
    }),
    [
      question,
      file,
      fileInputVersion,
      status,
      result,
      error,
      setFile,
      analyze,
      reset,
    ],
  );

  return <OtherContext.Provider value={value}>{children}</OtherContext.Provider>;
}

export function useOther() {
  const context = useContext(OtherContext);
  if (!context) {
    throw new Error("useOther must be used within an OtherProvider.");
  }
  return context;
}
