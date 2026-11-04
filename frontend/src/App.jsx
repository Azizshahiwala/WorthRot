import { useAnalysis } from "./contexts/AnalysisContext.jsx";
import { Card } from "./components/ui/Card.jsx";
import QuestionForm from "./components/youtube/QuestionForm.jsx";
import VerdictCard from "./components/youtube/VerdictCard.jsx";

export default function App() {
  const { status, result, error } = useAnalysis();

  return (
    <main className="page-shell">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">A little less scrolling, a lot more learning</p>
        <h1 id="page-title">Is this video worth your time?</h1>
        <p className="hero-copy">
          Tell us what you want to learn. Get a clear verdict with timestamped
          evidence, so you can watch with a purpose.
        </p>
      </section>

      <div className="analyzer-grid">
        <Card className="form-card">
          <QuestionForm />
        </Card>

        <section className="result-region" aria-live="polite">
          {status === "idle" && (
            <Card className="empty-result">
              <span className="empty-mark" aria-hidden="true">
                ↳
              </span>
              <h2>Your useful bits will show up here</h2>
              <p>
                Add a question and a video or transcript to get started. We’ll
                show what matches and what’s missing.
              </p>
            </Card>
          )}
          {status === "loading" && (
            <Card className="loading-result">
              <span className="spinner spinner-md" role="status">
                <span className="visually-hidden">Analyzing video</span>
              </span>
              <p>Looking for useful evidence…</p>
            </Card>
          )}
          {status === "error" && (
            <Card className="error-result" role="alert">
              <h2>We couldn’t analyze this video</h2>
              <p>{error}</p>
            </Card>
          )}
          {status === "success" && <VerdictCard result={result} />}
        </section>
      </div>
    </main>
  );
}
