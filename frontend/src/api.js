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
    throw new Error(result.message || "The request could not be completed.");
  }

  return result;
}
