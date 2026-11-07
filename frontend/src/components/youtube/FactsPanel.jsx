import { Card } from "../ui/Card.jsx";
import Badge from "../ui/Badge.jsx";
import GapCheck from "../ui/GapCheck.jsx";
import { getTranscriptLabel } from "../../lib/language.js";

const verdictVariants = {
  "Worth it": "worth",
  Skim: "skim",
  Rot: "rot",
  "Can't verify": "unverified",
};

export default function FactsPanel({ result }) {
  const verdict = result?.verdict || "Can't verify";
  const facts = Array.isArray(result?.facts) ? result.facts : [];
  const missing = Array.isArray(result?.missing) ? result.missing : [];
  const meta = result?.meta;
  const language = meta?.questionLanguage;
  const transcriptLabel = getTranscriptLabel(meta);

  return (
    <Card className="verdict-card" variant="elevated">
      <Badge variant={verdictVariants[verdict] || "unverified"}>{verdict}</Badge>
      {transcriptLabel && (
        <p className="transcript-language" aria-label="Transcript language">
          {transcriptLabel}
        </p>
      )}
      {meta?.retrievalTranslationFailed && (
        <p className="language-confidence-note" role="note">
          Cross-language matching was best-effort; confidence may be lower.
        </p>
      )}

      {facts.length > 0 && (
        <ul className="facts-list" aria-label="Verified facts">
          {facts.map((fact, index) => (
            <li className="fact-item" key={`${fact.timestamp}-${index}`}>
              <span lang={language || undefined} dir="auto">{fact.text}</span>
              {fact.url ? (
                <a
                  className="timestamp-link"
                  href={fact.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {fact.timestamp}
                  <span className="visually-hidden"> (opens video)</span>
                </a>
              ) : fact.timestamp ? (
                <span className="timestamp">{fact.timestamp}</span>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {missing.length > 0 && (
        <ul className="missing-chips" aria-label="Missing topics">
          {missing.map((item, index) => (
            <li key={`${item}-${index}`} lang={language || undefined} dir="auto">
              {item}
            </li>
          ))}
        </ul>
      )}

      <GapCheck gap={result?.gap} language={language} />

      {import.meta.env.DEV && meta && (
        <small className="analysis-meta">
          {meta.tokens_in} in / {meta.tokens_out} out
          {meta.cached && <span className="cached-tag">Cached</span>}
        </small>
      )}
    </Card>
  );
}
