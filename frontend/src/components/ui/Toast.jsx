import Button from "./Button.jsx";

export default function Toast({ id, message, type = "info", onDismiss }) {
  return (
    <div
      className={`toast toast-${type}`}
      role={type === "error" ? "alert" : "status"}
    >
      <p>{message}</p>
      <Button
        variant="ghost"
        size="sm"
        aria-label="Dismiss notification"
        onClick={() => onDismiss(id)}
      >
        ×
      </Button>
    </div>
  );
}
