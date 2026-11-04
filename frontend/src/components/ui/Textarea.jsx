import { useId } from "react";

export default function Textarea({
  id,
  label,
  error,
  hint,
  className = "",
  ...props
}) {
  const generatedId = useId();
  const textareaId = id || generatedId;
  const descriptionId = `${textareaId}-description`;

  return (
    <div className={`field ${className}`.trim()}>
      <label className="field-label" htmlFor={textareaId}>
        {label}
      </label>
      <textarea
        {...props}
        id={textareaId}
        className={`text-input text-area${error ? " has-error" : ""}`}
        aria-invalid={Boolean(error)}
        aria-describedby={error || hint ? descriptionId : undefined}
      />
      {(error || hint) && (
        <span
          className={`field-description${error ? " field-error" : ""}`}
          id={descriptionId}
        >
          {error || hint}
        </span>
      )}
    </div>
  );
}
