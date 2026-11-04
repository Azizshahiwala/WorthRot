function timestampSeconds(timestamp) {
  if (typeof timestamp !== "string") return null;
  const parts = timestamp.split(":").map(Number);
  if (
    parts.length < 2 ||
    parts.length > 3 ||
    parts.some((part) => !Number.isInteger(part) || part < 0)
  ) {
    return null;
  }
  return parts.reduce((total, part) => total * 60 + part, 0);
}

function timestampUrl(videoUrl, timestamp) {
  const seconds = timestampSeconds(timestamp);
  if (seconds === null || !videoUrl) return null;

  let link;
  try {
    link = new URL(videoUrl);
  } catch (error) {
    if (error instanceof TypeError) return null;
    throw error;
  }

  const isYouTube =
    link.hostname === "youtube.com" ||
    link.hostname.endsWith(".youtube.com") ||
    link.hostname === "youtu.be" ||
    link.hostname.endsWith(".youtu.be");
  if (!isYouTube) return null;
  link.searchParams.set("t", String(seconds));
  return link.href;
}

export default function EvidenceList({ evidence = [], videoUrl }) {
  return (
    <section className="evidence-section" aria-labelledby="evidence-heading">
      <h3 id="evidence-heading">Evidence</h3>
      {evidence.length === 0 ? (
        <p>No verified timestamped quotes were returned.</p>
      ) : (
        <ul className="evidence-list">
          {evidence.map((item, index) => {
            const href = timestampUrl(item.timestamp || "", item.url || videoUrl);
            return (
              <li className="evidence-item" key={`${item.timestamp}-${index}`}>
                <blockquote>“{item.quote}”</blockquote>
                {href ? (
                  <a
                    className="timestamp-link"
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {item.timestamp}
                    <span className="visually-hidden"> (opens video)</span>
                  </a>
                ) : (
                  <span className="timestamp">{item.timestamp}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
