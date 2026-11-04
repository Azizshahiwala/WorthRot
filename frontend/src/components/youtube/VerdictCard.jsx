import { Card } from "../ui/Card.jsx";
import Badge from "../ui/Badge.jsx";
import EvidenceList from "./EvidenceList.jsx";

const verdictVariants = {
  "Worth it": "worth",
  Skim: "skim",
  Rot: "rot",
  "Can't verify": "unverified",
};

function hasTimestamp(value) {
  return (
    typeof value === "string" &&
    /^(?:\d+:[0-5]\d|\d+:[0-5]\d:[0-5]\d)$/.test(value)
  );
}

export default function VerdictCard({ result }) {
  const requestedVerdict = result?.verdict || "Can't verify";
  const responseEvidence = Array.isArray(result?.evidence) ? result.evidence : [];
  const evidence = responseEvidence.filter(
    (item) =>
      typeof item?.quote === "string" &&
      item.quote.trim() &&
      hasTimestamp(item.timestamp),
  );
  const verdict =
    ["Worth it", "Skim"].includes(requestedVerdict) && evidence.length === 0
      ? "Can't verify"
      : requestedVerdict;
  const missing = Array.isArray(result?.missing) ? result.missing : [];
  const confidence = Number.isFinite(result?.confidence)
    ? Math.round(result.confidence * 100)
    : null;

  return (
    <Card className="verdict-card" variant="elevated">
      <div className="verdict-heading">
        <div>
          <span className="step-label">Your video verdict</span>
          <h2>Here’s what we found</h2>
        </div>
        <Badge variant={verdictVariants[verdict] || "unverified"}>{verdict}</Badge>
      </div>

      {confidence !== null && (
        <p className="confidence">
          Confidence <strong>{confidence}%</strong>
        </p>
      )}

      <EvidenceList evidence={evidence} videoUrl={result?.url} />

      <section className="missing-section" aria-labelledby="missing-heading">
        <h3 id="missing-heading">Still missing</h3>
        {missing.length > 0 ? (
          <ul>
            {missing.map((item, index) => (
              <li key={`${item}-${index}`}>{item}</li>
            ))}
          </ul>
        ) : (
          <p>No gaps were reported.</p>
        )}
      </section>
    </Card>
  );
}
