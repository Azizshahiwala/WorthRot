const partLabels = {
  covered: ["✅", "Covered"],
  partial: ["◐", "Partly covered"],
  missing: ["❌", "Missing"],
};

export default function GapCheck({ gap }) {
  if (!gap || !Array.isArray(gap.parts) || gap.parts.length === 0) return null;

  return (
    <section className="evidence-summary gap-check" aria-label="Question gap check">
      <p>
        <strong>Gap check:</strong> {gap.covered} of {gap.total} parts covered.
      </p>
      <ul className="gap-part-list">
        {gap.parts.map((part, index) => {
          const [symbol, label] = partLabels[part.status] || partLabels.missing;
          return (
            <li key={`${part.text}-${index}`}>
              <span aria-hidden="true">{symbol}</span>{" "}
              <strong>{label}:</strong> {part.text}
            </li>
          );
        })}
      </ul>
      <small>Based on the checked facts, not necessarily the whole video.</small>
    </section>
  );
}
