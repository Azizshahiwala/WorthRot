import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import HistoryItem from "../components/history/HistoryItem.jsx";
import Button from "../components/ui/Button.jsx";
import { useHistory } from "../contexts/HistoryContext.jsx";

export default function HistoryPage() {
  const { entries, available, removeEntry, clearHistory } = useHistory();
  const [confirmClear, setConfirmClear] = useState(false);
  const [announcement, setAnnouncement] = useState("");

  useEffect(() => {
    if (!confirmClear) return undefined;
    const timer = window.setTimeout(() => setConfirmClear(false), 4000);
    return () => window.clearTimeout(timer);
  }, [confirmClear]);

  function handleDelete(entry) {
    if (removeEntry(entry.id)) {
      setAnnouncement(`Removed analysis: ${entry.question}`);
    }
  }

  function handleClear() {
    if (!confirmClear) {
      setConfirmClear(true);
      return;
    }
    const hadEntries = clearHistory();
    setConfirmClear(false);
    setAnnouncement(hadEntries ? "History cleared." : "History is already empty.");
  }

  return (
    <main className="page-shell history-page">
      <header className="history-heading">
        <div>
          <p className="eyebrow">WorthRot / The watch ledger</p>
          <h1>Your saved verdicts</h1>
          <p className="history-intro">
            Questions you’ve already put to the test.
          </p>
        </div>
        <div className="history-count" aria-label={`${entries.length} saved analyses`}>
          <strong>{String(entries.length).padStart(2, "0")}</strong>
          <span>FILED</span>
        </div>
      </header>

      <div className="history-toolbar">
        <p className="history-device-note">Saved on this device only.</p>
        {entries.length > 0 && (
          <Button
            variant="secondary"
            size="sm"
            onClick={handleClear}
            onBlur={() => setConfirmClear(false)}
          >
            {confirmClear ? "Confirm clear all" : "Clear all"}
          </Button>
        )}
      </div>

      {!available && (
        <p className="history-storage-notice" role="status">
          History can’t be saved in this browser. Your analyses remain
          available for this session.
        </p>
      )}

      <p className="visually-hidden" role="status" aria-live="polite">
        {announcement}
      </p>

      {entries.length === 0 ? (
        <p className="history-empty">
          No verdicts filed yet. Start with{" "}
          <Link to="/">YouTube</Link> or <Link to="/other">Other</Link>.
        </p>
      ) : (
        <ul className="history-list" aria-label="Saved analyses">
          {entries.map((entry) => (
            <HistoryItem
              key={entry.id}
              entry={entry}
              onDelete={handleDelete}
            />
          ))}
        </ul>
      )}
    </main>
  );
}
