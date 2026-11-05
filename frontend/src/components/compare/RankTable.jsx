import Badge from "../ui/Badge.jsx";

const verdictVariants = {
  "Worth it": "worth",
  Skim: "skim",
  Rot: "rot",
  "Can't verify": "unverified",
};

export default function RankTable({ ranking }) {
  return (
    <div className="rank-table-scroll">
      <table className="rank-table">
        <caption>Video rankings</caption>
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Video</th>
            <th scope="col">Verdict</th>
            <th scope="col">Verified facts</th>
            <th scope="col">First fact</th>
          </tr>
        </thead>
        <tbody>
          {ranking.map((video) => {
            const firstFact = video.facts[0];
            return (
              <tr key={video.videoId}>
                <th scope="row">{video.rank}</th>
                <td>
                  <a
                    className="rank-video-link"
                    href={video.url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {video.videoId}
                    <span className="visually-hidden"> (opens video)</span>
                  </a>
                </td>
                <td>
                  <Badge variant={verdictVariants[video.verdict]}>
                    {video.verdict}
                  </Badge>
                </td>
                <td>{video.facts.length}</td>
                <td>
                  {firstFact?.url ? (
                    <a
                      className="timestamp-link"
                      href={firstFact.url}
                      target="_blank"
                      rel="noreferrer"
                      aria-label={
                        `First verified fact at ${firstFact.timestamp} ` +
                        `for ${video.videoId}`
                      }
                    >
                      {firstFact.timestamp}
                    </a>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
