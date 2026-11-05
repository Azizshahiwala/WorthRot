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

function isCompareResult(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    typeof value.question === "string" &&
    (typeof value.best === "string" || value.best === null) &&
    Array.isArray(value.ranking) &&
    value.ranking.every(
      (item) =>
        item !== null &&
        typeof item === "object" &&
        Number.isInteger(item.rank) &&
        typeof item.videoId === "string" &&
        typeof item.url === "string" &&
        verdicts.has(item.verdict) &&
        Array.isArray(item.facts) &&
        item.facts.every(
          (fact) =>
            fact !== null &&
            typeof fact === "object" &&
            typeof fact.text === "string" &&
            typeof fact.timestamp === "string" &&
            typeof fact.url === "string",
        ) &&
        Array.isArray(item.missing) &&
        item.missing.every((entry) => typeof entry === "string") &&
        (item.error === null ||
          (item.error !== null &&
            typeof item.error === "object" &&
            typeof item.error.message === "string")) &&
        item.meta !== null &&
        typeof item.meta === "object" &&
        typeof item.meta.cached === "boolean" &&
        Number.isInteger(item.meta.tokens_in) &&
        Number.isInteger(item.meta.tokens_out),
    ) &&
    value.meta !== null &&
    typeof value.meta === "object" &&
    Number.isInteger(value.meta.tokens_in_total) &&
    Number.isInteger(value.meta.tokens_out_total)
  );
}

export async function compare({ question, urls }) {
  const response = await fetch("/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, urls }),
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
    throw new Error(
      errorPayload.message || "The request could not be completed.",
    );
  }
  if (!isCompareResult(result)) {
    throw new Error("The server returned an invalid comparison response.");
  }
  return result;
}

const mediaSources = new Set(["subtitles", "speech", "frames"]);

function isMediaAnalysisResponse(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    verdicts.has(value.verdict) &&
    mediaSources.has(value.source) &&
    Array.isArray(value.facts) &&
    value.facts.every(
      (fact) =>
        fact !== null &&
        typeof fact === "object" &&
        typeof fact.text === "string" &&
        (typeof fact.timestamp === "string" || fact.timestamp === null) &&
        fact.url === null,
    ) &&
    Array.isArray(value.missing) &&
    value.missing.every((entry) => typeof entry === "string") &&
    value.meta !== null &&
    typeof value.meta === "object" &&
    Number.isInteger(value.meta.tokens_in) &&
    Number.isInteger(value.meta.tokens_out) &&
    Number.isInteger(value.meta.frames_sent)
  );
}

export async function analyzeMedia(formData) {
  const response = await fetch("/analyze-media", {
    method: "POST",
    body: formData,
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
    throw new Error(
      errorPayload.message || "The media request could not be completed.",
    );
  }
  if (!isMediaAnalysisResponse(result)) {
    throw new Error("The server returned an invalid media analysis response.");
  }
  return result;
}
