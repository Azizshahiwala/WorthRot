import { useAnalysis } from "../../contexts/AnalysisContext.jsx";
import { useToast } from "../../contexts/ToastContext.jsx";
import { useRateLimit } from "../../contexts/RateLimitContext.jsx";
import RateLimitNotice from "../RateLimitNotice.jsx";
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
  const { limits } = useRateLimit();
  const isLoading = status === "loading";
  const limitReached = limits.analyze?.remaining === 0;

  async function handleSubmit(event) {
    event.preventDefault();
    try {
      await analyze();
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  return (
    <form className="question-form" onSubmit={handleSubmit}>
      <div className="form-heading">
        <span className="step-label">
          <span className="step-number">01</span> The question
        </span>
        <h2>What do you want to know?</h2>
        <p>We’ll look for answers in the video, not just its title.</p>
      </div>

      <Input
        label="Your question"
        name="question"
        placeholder="Does this video explains photosynthesis?"
        autoComplete="off"
        required
        disabled={isLoading}
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
      />

      <Input
        label="YouTube URL"
        name="url"
        type="url"
        placeholder="youtube.com/watch?v=..."
        autoComplete="url"
        disabled={isLoading}
        value={url}
        onChange={(event) => setUrl(event.target.value)}
      />

      <details className="transcript-details">
        <summary>Or paste a transcript instead</summary>
        <Textarea
          className="transcript-field"
          label="Video transcript"
          name="transcript"
          rows={6}
          disabled={isLoading}
          placeholder="[00:12] Paste a transcript line with its timestamp..."
          hint="Include timestamps such as [00:12] so each fact can be verified."
          value={transcript}
          onChange={(event) => setTranscript(event.target.value)}
        />
      </details>

      <Button
        type="submit"
        className="submit-button"
        size="lg"
        loading={isLoading}
        disabled={isLoading || limitReached}
      >
        {isLoading ? "Checking your video" : "Get the verdict"}
        {!isLoading && <span aria-hidden="true">→</span>}
      </Button>
      <RateLimitNotice feature="analyze" />
      <p className="privacy-note">
        No playback, downloads, or made-up answers. Just useful evidence.
      </p>
    </form>
  );
}
