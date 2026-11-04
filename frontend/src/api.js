export async function analyzeVideo({ question, url }) {
  const response = await fetch("/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, urls: [url] }),
  });
  const result = await response.json();

  if (!response.ok) {
    throw new Error(result.message || "The request could not be completed.");
  }

  return result;
}
