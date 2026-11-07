export function getLanguageName(code) {
  if (typeof code !== "string" || !code || code === "und") return "Unknown";
  try {
    return new Intl.DisplayNames(undefined, { type: "language" }).of(code) || code;
  } catch {
    return code;
  }
}

export function getTranscriptLabel(meta) {
  if (!meta || meta.transcriptSource === "frames") return "";
  const language = getLanguageName(
    meta.transcriptOriginalLanguage || meta.transcriptLanguage,
  );
  if (meta.transcriptSource === "translated") {
    return `Translated from ${language}`;
  }
  const source = {
    auto: "auto-generated",
    manual: "manual transcript",
    speech: "speech recognition",
    subtitles: "embedded subtitles",
  }[meta.transcriptSource];
  return source ? `Transcript: ${language}, ${source}` : "";
}
