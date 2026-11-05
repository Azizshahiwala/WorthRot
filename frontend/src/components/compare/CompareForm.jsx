import { useCompare } from "../../contexts/CompareContext.jsx";
import { useToast } from "../../contexts/ToastContext.jsx";
import { useRateLimit } from "../../contexts/RateLimitContext.jsx";
import RateLimitNotice from "../RateLimitNotice.jsx";
import Button from "../ui/Button.jsx";
import Input from "../ui/Input.jsx";

export default function CompareForm() {
  const {
    question,
    setQuestion,
    urls,
    setUrl,
    addUrl,
    removeUrl,
    compare,
    status,
    error,
  } = useCompare();
  const { showToast } = useToast();
  const { limits } = useRateLimit();
  const loading = status === "loading";
  const limitReached = limits.compare?.remaining === 0;

  function handleSubmit(event) {
    event.preventDefault();
    void compare().catch((error) => showToast(error.message, "error"));
  }

  return (
    <form className="compare-form" onSubmit={handleSubmit}>
      <Input
        label="Your question"
        name="question"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        required
        disabled={loading}
      />
      <div className="compare-url-list">
        {urls.map((url, index) => (
          <div className="compare-url-row" key={index}>
            <Input
              id={`compare-url-${index}`}
              label={`YouTube URL ${index + 1}`}
              name={`url-${index + 1}`}
              type="url"
              value={url}
              onChange={(event) => setUrl(index, event.target.value)}
              required
              disabled={loading}
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              aria-label={`Remove video ${index + 1} URL`}
              disabled={loading || urls.length <= 2}
              onClick={() => removeUrl(index)}
            >
              Remove
            </Button>
          </div>
        ))}
      </div>
      <div className="compare-form-actions">
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={addUrl}
          disabled={loading || urls.length >= 3}
        >
          Add another video
        </Button>
        <Button type="submit" disabled={loading || limitReached}>
          Compare videos
        </Button>
      </div>
      <RateLimitNotice feature="compare" />
      {loading && (
        <span className="compare-loading-label" role="status">
          Comparing videos
        </span>
      )}
      {status === "error" && (
        <div className="inline-error" role="alert">
          {error}
        </div>
      )}
    </form>
  );
}
