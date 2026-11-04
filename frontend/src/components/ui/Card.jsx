export function Card({
  children,
  className = "",
  variant = "default",
  ...props
}) {
  return (
    <div
      {...props}
      className={`card card-${variant} ${className}`.trim()}
    >
      {children}
    </div>
  );
}
