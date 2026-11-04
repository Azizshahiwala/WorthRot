const verdictLabels = {
  worth: "Worth it",
  skim: "Skim",
  rot: "Rot",
  unverified: "Can't verify",
};

export default function Badge({ variant = "unverified", children, size = "md" }) {
  const label = children || verdictLabels[variant] || verdictLabels.unverified;
  const safeVariant = verdictLabels[variant] ? variant : "unverified";

  return (
    <span className={`badge badge-${safeVariant} badge-${size}`}>
      {label}
    </span>
  );
}
