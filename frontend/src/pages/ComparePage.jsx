import { Card } from "../components/ui/Card.jsx";
import Spinner from "../components/ui/Spinner.jsx";
import CompareForm from "../components/compare/CompareForm.jsx";
import CompareResultList from "../components/compare/CompareResultList.jsx";
import RankTable from "../components/compare/RankTable.jsx";
import { useCompare } from "../contexts/CompareContext.jsx";

export default function ComparePage() {
  const { status, result } = useCompare();

  return (
    <main className="page-shell compare-page">
      <header className="compare-heading">
        <p className="eyebrow">WorthRot / Side-by-side</p>
        <h1>Compare videos</h1>
      </header>
      <Card className="compare-form-card">
        <CompareForm />
      </Card>
      {status === "loading" && (
        <div className="compare-loading" aria-live="polite">
          <Spinner label="Comparing videos" />
          <span>Comparing videos</span>
        </div>
      )}
      {status === "success" && result && (
        <section className="compare-results" aria-live="polite">
          {result.best === null && (
            <p className="compare-best-none">
              None of these videos cover your question.
            </p>
          )}
          <RankTable ranking={result.ranking} />
          <CompareResultList ranking={result.ranking} />
          {import.meta.env.DEV && (
            <small className="analysis-meta">
              {result.meta.tokens_in_total} in / {result.meta.tokens_out_total} out
            </small>
          )}
        </section>
      )}
    </main>
  );
}
