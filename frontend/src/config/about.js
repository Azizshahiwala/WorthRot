export const about = {
  hero: {
    title: "Is this video worth your time?",
    subtitle: "Ask a question. Get facts from the video, with timestamps.",
  },
  sectionTitles: {
    steps: "How it works",
    principles: "Principles",
    limits: "Limits",
    builtWith: "Built with",
  },
  steps: [
    {
      number: 1,
      title: "Ask",
      description: "Enter your question and a YouTube link.",
    },
    {
      number: 2,
      title: "Check",
      description: "We read the captions and find the parts that match.",
    },
    {
      number: 3,
      title: "Verify",
      description:
        "Every fact is checked against the transcript before you see it.",
    },
  ],
  principles: [
    {
      title: "Facts only",
      description: "Short answers with timestamps. No summaries.",
    },
    {
      title: "Verified",
      description: "Facts that can't be found in the transcript are dropped.",
    },
    {
      title: "No guessing",
      description: "If the video doesn't answer it, we say so.",
    },
    {
      title: "Private by default",
      description:
        "No accounts, no cookies. A hashed IP is kept for up to 2 days to enforce the daily limit. Uploaded files are deleted after processing.",
    },
  ],
  limits: [
    "Each feature allows 10 requests per day per network.",
    "Works with YouTube videos that have captions.",
    "Results are only as good as the transcript.",
    "Other video platforms are not supported.",
    "The Other tab accepts MP4 and MP3 files up to a size and length cap.",
    "WorthRot can make mistakes. Check the video if it matters.",
  ],
  builtWith:
    "Flask, React, and Bazaarlink's OpenAI-compatible API. " +
    "Hosted on Embarko. Built for the Embarko AI hackathon.",
  author: {
    name: "", // Fill these in with the project owner's details.
    role: "",
    githubUrl: "",
    projectRepoUrl: "",
    githubLabel: "WorthRot on GitHub",
    projectRepoLabel: "WorthRot project repository",
  },
};
