export default function StepList({ steps }) {
  return (
    <ol className="about-step-list">
      {steps.map((step) => (
        <li key={step.number}>
          <span className="about-step-number" aria-hidden="true">
            {String(step.number).padStart(2, "0")}
          </span>
          <div className="about-step-copy">
            <h3>{step.title}</h3>
            <p>{step.description}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}
