import { Card } from "../ui/Card.jsx";
import Badge from "../ui/Badge.jsx";

const verdictVariants = {
  "Worth it": "worth",
  Skim: "skim",
  Rot: "rot",
  "Can't verify": "unverified",
};

export default function VerdictCard({ result }) {
  const verdict = result?.verdict || "Can't verify";
  const facts = Array.isArray(result?.facts) ? result.facts : [];
  const missing = Array.isArray(result?.missing) ? result.missing : [];
  const meta = result?.meta;

  return (
    <Card className="verdict-card" variant="elevated">
      <Badge variant={verdictVariants[verdict] || "unverified"}>{verdict}</Badge>

      {facts.length > 0 && (
        <ul className="facts-list" aria-label="Verified facts">
          {facts.map((fact, index) => (
            <li className="fact-item" key={`${fact.timestamp}-${index}`}>
              <span>{fact.text}</span>
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
              ) : (
                <span className="timestamp">{fact.timestamp}</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {missing.length > 0 && (
        <ul className="missing-chips" aria-label="Missing topics">
          {missing.map((item, index) => (
            <li key={`${item}-${index}`}>{item}</li>
          ))}
        </ul>
      )}

      {import.meta.env.DEV && meta && (
        <small className="analysis-meta">
          {meta.tokens_in} in / {meta.tokens_out} out
          {meta.cached && <span className="cached-tag">Cached</span>}
        </small>
      )}
    </Card>
  );
}
