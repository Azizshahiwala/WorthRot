import { Card } from "./ui/Card.jsx";

export default function ComingSoon({ title }) {
  return (
    <main className="page-shell placeholder-page">
      <Card className="placeholder-card">
        <span className="placeholder-kicker">On the watchlist</span>
        <h1>{title}</h1>
        <p>
          We’re making this part useful. For now, the YouTube analyzer is ready
          to explore.
        </p>
      </Card>
    </main>
  );
}
