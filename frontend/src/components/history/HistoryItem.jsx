import { useState } from "react";
import { X } from "lucide-react";
import Badge from "../ui/Badge.jsx";
import Button from "../ui/Button.jsx";
import FactsPanel from "../youtube/FactsPanel.jsx";
import AgreementBlock from "../compare/AgreementBlock.jsx";
import CompareResultList from "../compare/CompareResultList.jsx";
import RankTable from "../compare/RankTable.jsx";

const verdictVariants = {
  "Worth it": "worth",
  Skim: "skim",
  Rot: "rot",
};

function getVideoLabel(entry) {
  if (entry.source === "compare") return "Compared videos";
  if (entry.source === "media") return "Other upload";
  if (entry.source === "transcript") return "Pasted transcript";
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
            <X aria-hidden="true" size={18} />
          </Button>
        </div>
        <div
          className="history-entry-details"
          id={detailsId}
          hidden={!expanded}
        >
          {entry.comparison ? (
            <>
              <RankTable ranking={entry.comparison.ranking} />
              <AgreementBlock
                agreement={entry.comparison.agreement}
                ranking={entry.comparison.ranking}
              />
              <CompareResultList ranking={entry.comparison.ranking} />
            </>
          ) : (
            <FactsPanel
              result={{
                verdict: entry.verdict,
                facts: entry.facts,
                missing: entry.missing,
                gap: entry.gap,
              }}
            />
          )}
        </div>
      </article>
    </li>
  );
}
