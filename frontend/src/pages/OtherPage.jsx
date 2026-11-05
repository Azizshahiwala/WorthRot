import Badge from "../components/ui/Badge.jsx";
import { Card } from "../components/ui/Card.jsx";
import FactsPanel from "../components/youtube/FactsPanel.jsx";
import MediaForm from "../components/other/MediaForm.jsx";
import { useOther } from "../contexts/OtherContext.jsx";

export default function OtherPage() {
  const { status, result } = useOther();

  return (
    <main className="page-shell media-page">
      <header className="media-heading">
        <p className="eyebrow">WorthRot / Local files</p>
        <h1>Check a video or audio file</h1>
      </header>
      <Card className="media-form-card">
        <MediaForm />
      </Card>
      {status === "success" && result && (
        <section className="media-results" aria-live="polite">
          {result.source === "frames" && (
            <div className="media-source-label">
              <Badge variant="skim">From frames</Badge>
            </div>
          )}
          <FactsPanel result={result} />
        </section>
      )}
    </main>
  );
}
