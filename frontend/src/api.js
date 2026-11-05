const verdicts = new Set(["Worth it", "Skim", "Rot", "Can't verify"]);

function isAnalysisResponse(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    verdicts.has(value.verdict) &&
    Array.isArray(value.facts) &&
    value.facts.every(
      (fact) =>
        fact !== null &&
        typeof fact === "object" &&
        typeof fact.text === "string" &&
        typeof fact.timestamp === "string" &&
        typeof fact.url === "string",
    ) &&
    Array.isArray(value.missing) &&
    value.missing.every((item) => typeof item === "string") &&
    value.meta !== null &&
    typeof value.meta === "object" &&
    typeof value.meta.video_id === "string" &&
    typeof value.meta.cached === "boolean" &&
    Number.isInteger(value.meta.tokens_in) &&
    Number.isInteger(value.meta.tokens_out)
  );
}

export async function analyzeVideo({ question, url, transcript }) {
  const request = {
    question,
    urls: url.trim() ? [url.trim()] : [],
  };
  if (transcript.trim()) {
    request.transcript = transcript.trim();
  }

  const response = await fetch("/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error("The server returned an invalid response.");
  }

  if (!response.ok) {
    const errorPayload =
      result !== null && typeof result === "object" ? result : {};
    const error = new Error(
      errorPayload.message || "The request could not be completed.",
    );
    if (isAnalysisResponse(errorPayload.result)) {
      error.analysisResult = errorPayload.result;
    }
    throw error;
  }
  if (!isAnalysisResponse(result)) {
    throw new Error("The server returned an invalid analysis response.");
  }

  return result;
}
