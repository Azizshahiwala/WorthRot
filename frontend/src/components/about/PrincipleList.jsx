export default function PrincipleList({ principles }) {
  return (
    <ul className="about-principle-list">
      {principles.map((principle) => (
        <li key={principle.title}>
          <h3>{principle.title}</h3>
          <p>{principle.description}</p>
        </li>
      ))}
    </ul>
  );
}
