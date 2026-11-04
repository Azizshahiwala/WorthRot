import { useId } from "react";

export default function Input({
  id,
  label,
  error,
  hint,
  className = "",
  ...props
}) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const descriptionId = `${inputId}-description`;

  return (
    <div className={`field ${className}`.trim()}>
      <label className="field-label" htmlFor={inputId}>
        {label}
      </label>
      <input
        {...props}
        id={inputId}
        className={`text-input${error ? " has-error" : ""}`}
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
