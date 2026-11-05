import { useId } from "react";
import { MAX_UPLOAD_MB } from "../../config/limits.js";
import { useOther } from "../../contexts/OtherContext.jsx";
import { useToast } from "../../contexts/ToastContext.jsx";
import { useRateLimit } from "../../contexts/RateLimitContext.jsx";
import RateLimitNotice from "../RateLimitNotice.jsx";
import Button from "../ui/Button.jsx";
import Input from "../ui/Input.jsx";
import Spinner from "../ui/Spinner.jsx";

function formatFileSize(bytes) {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function MediaForm() {
  const fileInputId = useId();
  const {
    question,
    setQuestion,
    file,
    fileInputVersion,
    setFile,
    analyze,
    status,
    error,
  } = useOther();
  const { showToast } = useToast();
  const { limits } = useRateLimit();
  const loading = status === "loading";
  const limitReached = limits.media?.remaining === 0;

  function handleSubmit(event) {
    event.preventDefault();
    void analyze().catch((error) => showToast(error.message, "error"));
  }

  return (
    <form className="media-form" onSubmit={handleSubmit}>
      <Input
        label="Your question"
        name="question"
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
        required
        disabled={loading}
      />
      <div className="media-file-field">
        <label className="field-label" htmlFor={fileInputId}>
          Video or audio file
        </label>
        <input
          key={fileInputVersion}
          className="text-input media-file-input"
          id={fileInputId}
          name="file"
          type="file"
          accept=".mp4,.mp3,video/mp4,audio/mpeg"
          onChange={(event) => setFile(event.target.files?.[0] || null)}
          disabled={loading}
          aria-describedby={`${fileInputId}-description`}
        />
        <span className="field-description" id={`${fileInputId}-description`}>
          MP4 or MP3, up to {MAX_UPLOAD_MB} MB.
        </span>
        {file && (
          <span className="media-file-name">
            {file.name} · {formatFileSize(file.size)}
          </span>
        )}
      </div>
      <p className="media-privacy-note">
        Files are processed on the server and deleted afterwards. Audio or
        frames may be sent to an AI provider.
      </p>
      <div className="media-form-actions">
        <Button type="submit" disabled={loading || limitReached}>
          Analyze file
        </Button>
      </div>
      <RateLimitNotice feature="media" />
      {loading && (
        <div className="media-loading" aria-live="polite">
          <Spinner label="Checking your file" />
          <span>Checking your file</span>
        </div>
      )}
      {status === "error" && (
        <div className="inline-error" role="alert">
          {error}
        </div>
      )}
    </form>
  );
}
