import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import AgreementBlock from "./AgreementBlock.jsx";

afterEach(cleanup);

describe("AgreementBlock", () => {
  it("maps video letters to ranked video IDs", () => {
    render(
      <AgreementBlock
        agreement={{
          agree: [{ point: "Needs a 12V supply", videos: ["A", "B"] }],
          disagree: [
            {
              point: "Setup time",
              positions: [
                { video: "A", claim: "ten minutes" },
                { video: "B", claim: "about an hour" },
              ],
            },
          ],
          unanswered: ["warranty"],
        }}
        ranking={[
          { rank: 1, videoId: "video-one" },
          { rank: 2, videoId: "video-two" },
        ]}
      />,
    );

    expect(screen.getByText(/Needs a 12V supply/).textContent).toContain(
      "A (Rank 1, video-one), B (Rank 2, video-two)",
    );
    expect(screen.getByText(/Setup time/).textContent).toContain(
      "A (Rank 1, video-one) says ten minutes",
    );
    expect(screen.getByText(/warranty/)).toBeTruthy();
  });

  it("hides null and provides plain fallbacks for empty lists", () => {
    const { rerender } = render(
      <AgreementBlock agreement={null} ranking={[]} />,
    );
    expect(screen.queryByLabelText(/Cross-video agreement/)).toBeNull();
    rerender(
      <AgreementBlock
        agreement={{ agree: [], disagree: [], unanswered: [] }}
        ranking={[]}
      />,
    );
    expect(screen.getByText("No clear disagreements found.")).toBeTruthy();
  });
});
