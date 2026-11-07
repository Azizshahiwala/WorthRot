import FactsPanel from "../youtube/FactsPanel.jsx";
import Badge from "../ui/Badge.jsx";

export default function CompareResultList({ ranking }) {
  return (
    <div className="compare-result-list">
      {ranking.map((video) => (
        <section
          className="compare-video-result"
          key={video.videoId}
          aria-labelledby={`compare-video-${video.videoId}`}
        >
          <h3 id={`compare-video-${video.videoId}`}>
            Rank {video.rank}:{" "}
            <a href={video.url} target="_blank" rel="noreferrer">
              {video.videoId}
              <span className="visually-hidden"> (opens video)</span>
            </a>
          </h3>
          {video.error ? (
            <div className="compare-check-error">
              <Badge variant="unverified">Could not check</Badge>
              <span>{video.error.message}</span>
            </div>
          ) : (
            <FactsPanel
              result={{
                verdict: video.verdict,
                facts: video.facts,
                missing: video.missing,
                gap: video.gap,
              }}
            />
          )}
        </section>
      ))}
    </div>
  );
}
