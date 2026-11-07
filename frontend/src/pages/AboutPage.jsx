import AboutSection from "../components/about/AboutSection.jsx";
import PrincipleList from "../components/about/PrincipleList.jsx";
import StepList from "../components/about/StepList.jsx";
import { about } from "../config/about.js";

export default function AboutPage() {
  const { author } = about;
  const showAuthor = [
    author.name,
    author.role,
    author.githubUrl,
    author.projectRepoUrl,
  ].some((value) => value.trim());

  return (
    <main className="page-shell about-page">
      <header className="about-hero">
        <h1>{about.hero.title}</h1>
        <p>{about.hero.subtitle}</p>
      </header>

      <AboutSection
        id="about-steps"
        title={about.sectionTitles.steps}
        className="about-workflow"
      >
        <StepList steps={about.steps} />
      </AboutSection>

      <AboutSection
        id="about-principles"
        title={about.sectionTitles.principles}
      >
        <PrincipleList principles={about.principles} />
      </AboutSection>

      <AboutSection
        id="about-latest-changes"
        title={about.sectionTitles.latestChanges}
      >
        <PrincipleList principles={about.latestChanges} />
      </AboutSection>

      <AboutSection id="about-limits" title={about.sectionTitles.limits}>
        <ul className="about-limits-list">
          {about.limits.map((limit) => (
            <li key={limit}>{limit}</li>
          ))}
        </ul>
      </AboutSection>

      <AboutSection id="about-built-with" title={about.sectionTitles.builtWith}>
        <p className="about-built-with-copy">{about.builtWith}</p>
      </AboutSection>

      {showAuthor && (
        <AboutSection
          id="about-author"
          title={about.sectionTitles.author}
        >
          <div className="about-author">
            {author.name && <h3>{author.name}</h3>}
            {author.role && <p>{author.role}</p>}
            <ul>
              {author.githubUrl && (
                <li>
                  <a
                    href={author.githubUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {author.githubLabel}
                  </a>
                </li>
              )}
              {author.projectRepoUrl && (
                <li>
                  <a
                    href={author.projectRepoUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {author.projectRepoLabel}
                  </a>
                </li>
              )}
            </ul>
          </div>
        </AboutSection>
      )}
    </main>
  );
}
