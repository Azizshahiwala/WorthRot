import { forwardRef } from "react";
import Spinner from "./Spinner.jsx";

const Button = forwardRef(function Button(
  {
    children,
    className = "",
    variant = "primary",
    size = "md",
    loading = false,
    disabled = false,
    type = "button",
    ...props
  },
  ref,
) {
  const classes = [
    "button",
    `button-${variant}`,
    `button-${size}`,
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      {...props}
      ref={ref}
      type={type}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      {loading && <Spinner size="sm" label="Loading" />}
      {children}
    </button>
  );
});

export default Button;
