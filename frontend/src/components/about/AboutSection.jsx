export default function AboutSection({ id, title, children, className = "" }) {
  return (
    <section
      className={`about-section ${className}`.trim()}
      aria-labelledby={`${id}-title`}
    >
      <h2 id={`${id}-title`}>{title}</h2>
      {children}
    </section>
  );
}
