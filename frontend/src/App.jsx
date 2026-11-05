import { useAnalysis } from "./contexts/AnalysisContext.jsx";
import { Card } from "./components/ui/Card.jsx";
import QuestionForm from "./components/youtube/QuestionForm.jsx";
import VerdictCard from "./components/youtube/VerdictCard.jsx";

export default function App() {
  const { status, result, error } = useAnalysis();

  return (
    <main className="page-shell">
      <section className="hero" aria-labelledby="page-title">
        <div className="hero-copy-block">
          <p className="eyebrow">Issue 01 / The video field guide</p>
          <h1 id="page-title">
            Is this video
            <br />
            <span className="hero-highlight">worth your time?</span>
          </h1>
          <p className="hero-copy">
            Bring a question. Get a verdict backed by timestamped proof, plus
            the gaps the video leaves behind.
          </p>
          <div className="hero-ledger" aria-label="What WorthRot checks">
            <span>
              <b>01</b> Your actual question
            </span>
            <span>
              <b>02</b> Timestamped evidence
            </span>
            <span>
              <b>03</b> What’s still missing
            </span>
          </div>
        </div>
        <aside className="hero-stamp" aria-label="Proof before play">
          <span className="stamp-top">WORTHROT / 001</span>
          <strong>
            Proof
            <br />
            before
            <br />
            play
          </strong>
          <span className="stamp-bottom">No title-only takes</span>
        </aside>
      </section>

      <div className="analyzer-grid">
        <Card className="form-card">
          <QuestionForm />
        </Card>

        <section className="result-region" aria-live="polite">
          {status === "idle" && (
            <Card className="empty-result">
              <span>No facts yet.</span>
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
            <>
              <Card className="error-result" role="alert">
                <h2>We couldn’t analyze this video</h2>
                <p>{error}</p>
              </Card>
              {result && <VerdictCard result={result} />}
            </>
          )}
          {status === "success" && <VerdictCard result={result} />}
        </section>
      </div>
    </main>
  );
}
