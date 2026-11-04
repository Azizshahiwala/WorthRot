import { useState } from "react";
import { useAnalysis } from "../../contexts/AnalysisContext.jsx";
import { useToast } from "../../contexts/ToastContext.jsx";
import Button from "../ui/Button.jsx";
import Input from "../ui/Input.jsx";
import Textarea from "../ui/Textarea.jsx";

export default function QuestionForm() {
  const {
    question,
    setQuestion,
    url,
    setUrl,
    transcript,
    setTranscript,
    status,
    analyze,
  } = useAnalysis();
  const { showToast } = useToast();
  const [validationError, setValidationError] = useState("");
  const isLoading = status === "loading";

  async function handleSubmit(event) {
    event.preventDefault();
    setValidationError("");
    if (!url.trim() && !transcript.trim()) {
      setValidationError("Add a YouTube URL or paste a transcript to continue.");
      return;
    }

    try {
      await analyze();
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  return (
    <form className="question-form" onSubmit={handleSubmit}>
      <div className="form-heading">
        <span className="step-label">Your next watch</span>
        <h2>What do you want to know?</h2>
        <p>We’ll look for answers in the video, not just its title.</p>
      </div>

      <Input
        label="Your question"
        name="question"
        placeholder="How do I make fresh pasta?"
        autoComplete="off"
        required
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
      />

      <Input
        label="YouTube URL"
        name="url"
        type="url"
        placeholder="youtube.com/watch?v=..."
        autoComplete="url"
        value={url}
        onChange={(event) => setUrl(event.target.value)}
      />

      <details className="transcript-details">
        <summary>Have a transcript? Paste it instead</summary>
        <Textarea
          className="transcript-field"
          label="Video transcript"
          name="transcript"
          rows={6}
          placeholder="Paste transcript text here..."
          value={transcript}
          onChange={(event) => setTranscript(event.target.value)}
        />
      </details>

      {validationError && (
        <p className="inline-error" role="alert">
          {validationError}
        </p>
      )}

      <Button
        type="submit"
        className="submit-button"
        size="lg"
        loading={isLoading}
        disabled={isLoading}
      >
        {isLoading ? "Checking your video" : "Find the useful bits"}
        {!isLoading && <span aria-hidden="true">→</span>}
      </Button>
      <p className="privacy-note">
        No playback, downloads, or made-up answers. Just useful evidence.
      </p>
    </form>
  );
}
