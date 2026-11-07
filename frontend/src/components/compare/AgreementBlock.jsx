function videoLabel(letter, ranking) {
  const video = ranking.find((item) => item.rank === letter.charCodeAt(0) - 64);
  return video
    ? `${letter} (Rank ${video.rank}, ${video.videoId})`
    : letter;
}

export default function AgreementBlock({ agreement, ranking }) {
  if (!agreement) return null;

  const agree = Array.isArray(agreement.agree) ? agreement.agree : [];
  const disagree = Array.isArray(agreement.disagree) ? agreement.disagree : [];
  const unanswered = Array.isArray(agreement.unanswered)
    ? agreement.unanswered
    : [];

  return (
    <section
      className="evidence-summary agreement-block"
      aria-label="Cross-video agreement based on checked facts"
    >
      <p>
        <strong>Agree:</strong>{" "}
        {agree.length
          ? agree.map((item, index) => (
              <span key={`${item.point}-${index}`}>
                {index > 0 && " · "}
                {item.point} —{" "}
                {item.videos.map((label) => videoLabel(label, ranking)).join(", ")}
              </span>
            ))
          : "No clear agreements found."}
      </p>
      <p>
        <strong>Disagree:</strong>{" "}
        {disagree.length
          ? disagree.map((item, index) => (
              <span key={`${item.point}-${index}`}>
                {index > 0 && " · "}
                {item.point}:{" "}
                {item.positions
                  .map(
                    (position) =>
                      `${videoLabel(position.video, ranking)} says ${position.claim}`,
                  )
                  .join("; ")}
              </span>
            ))
          : "No clear disagreements found."}
      </p>
      <p>
        <strong>Unanswered:</strong>{" "}
        {unanswered.length ? unanswered.join(" · ") : "No unanswered parts found."}
      </p>
      <small>Based on verified facts, not the full videos.</small>
    </section>
  );
}
