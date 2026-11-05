import { useRateLimit } from "../contexts/RateLimitContext.jsx";

function localResetTime(resetsAt) {
  const date = new Date(resetsAt);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

export default function RateLimitNotice({ feature }) {
  const { limits, error } = useRateLimit();
  const rate = limits[feature];
  const message =
    !rate
      ? error
        ? "Daily limit status unavailable."
        : "Checking daily limit…"
      : rate.remaining === 0
        ? `Daily limit reached.${localResetTime(rate.resetsAt) ? ` Resets at ${localResetTime(rate.resetsAt)}.` : ""}`
        : `${rate.remaining} of ${rate.limit} left today`;

  return (
    <p
      className={`rate-limit-notice${rate?.remaining === 0 ? " is-exhausted" : ""}`}
      role="status"
      aria-live="polite"
    >
      {message}
    </p>
  );
}
