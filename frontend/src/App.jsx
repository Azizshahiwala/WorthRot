import { useState } from "react";
import { analyzeVideo } from "./api.js";

export default function App() {
  const [question, setQuestion] = useState("");
  const [url, setUrl] = useState("");
  const [message, setMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setMessage("");
    setIsSubmitting(true);

    try {
      const result = await analyzeVideo({ question, url });
      setMessage(JSON.stringify(result));
    } catch (error) {
      setMessage(error.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="page">
      <header className="masthead">
        <a className="wordmark" href="/" aria-label="WorthRot home">
          worth<span>rot</span>
        </a>
        <span className="tagline">Make your next video worth the time.</span>
      </header>

      <section className="intro" aria-labelledby="page-title">
        <p className="eyebrow">A better way to watch</p>
        <h1 id="page-title">Will this video answer your question?</h1>
        <p className="description">
          Share what you want to learn and a YouTube link. WorthRot will help
          you decide whether to watch, skim, or skip.
        </p>

        <form className="analyze-form" onSubmit={handleSubmit}>
          <label htmlFor="question">What are you trying to find out?</label>
          <input
            id="question"
            name="question"
            placeholder="How do I make fresh pasta?"
            required
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />

          <label htmlFor="video-url">YouTube video URL</label>
          <input
            id="video-url"
            name="video-url"
            type="url"
            placeholder="https://www.youtube.com/watch?v=..."
            required
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />

          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Checking..." : "Check this video"}
          </button>
        </form>

        {message && (
          <p className="notice" role="status" aria-live="polite">
            {message}
          </p>
        )}
        <p className="starter-note">
          Starter project: the analysis endpoint is a placeholder and does not
          generate verdicts yet.
        </p>
      </section>
    </main>
  );
}
