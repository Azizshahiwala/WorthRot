export default function Spinner({ size = "md", label = "Loading" }) {
  return (
    <span className={`spinner spinner-${size}`} role="status">
      <span className="visually-hidden">{label}</span>
    </span>
  );
}
