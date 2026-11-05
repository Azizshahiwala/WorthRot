import { useState } from "react";
import Badge from "../ui/Badge.jsx";
import Button from "../ui/Button.jsx";
import FactsPanel from "../youtube/FactsPanel.jsx";

const verdictVariants = {
  "Worth it": "worth",
  Skim: "skim",
  Rot: "rot",
};

function getVideoLabel(entry) {
  if (!entry.url) return entry.videoId || "Pasted transcript";
  try {
    return new URL(entry.url).hostname.replace(/^www\./, "");
  } catch {
    return entry.videoId || "Video";
  }
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
  }).format(new Date(value));
}

export default function HistoryItem({ entry, onDelete }) {
  const [expanded, setExpanded] = useState(false);
  const date = new Date(entry.createdAt);
  const detailsId = `history-details-${entry.id}`;

  return (
    <li className="history-list-item">
      <article className={`history-entry${expanded ? " is-expanded" : ""}`}>
        <div className="history-entry-header">
          <button
            className="history-expand"
            type="button"
            aria-expanded={expanded}
            aria-controls={detailsId}
            onClick={() => setExpanded((current) => !current)}
          >
            <span className="history-entry-meta">
              <time dateTime={entry.createdAt}>{formatDate(entry.createdAt)}</time>
              <span aria-hidden="true">/</span>
              <span>{getVideoLabel(entry)}</span>
            </span>
            <span className="history-question">{entry.question}</span>
          </button>
          <Badge variant={verdictVariants[entry.verdict]} size="sm">
            {entry.verdict}
          </Badge>
          <Button
            className="history-delete"
            variant="ghost"
            size="sm"
            aria-label={`Delete analysis: ${entry.question}`}
            onClick={() => onDelete(entry)}
          >
            <span aria-hidden="true">×</span>
          </Button>
        </div>
        <div
          className="history-entry-details"
          id={detailsId}
          hidden={!expanded}
        >
          <FactsPanel
            result={{
              verdict: entry.verdict,
              facts: entry.facts,
              missing: entry.missing,
            }}
          />
        </div>
      </article>
    </li>
  );
}
