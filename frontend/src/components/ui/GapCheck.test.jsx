import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import GapCheck from "./GapCheck.jsx";

afterEach(cleanup);

describe("GapCheck", () => {
  it("shows a question-level count and accessible status labels", () => {
    render(
      <GapCheck
        gap={{
          covered: 2,
          total: 3,
          label: "Partly covered",
          parts: [
            { text: "setup cost", status: "covered" },
            { text: "required tools", status: "covered" },
            { text: "maintenance time", status: "missing" },
          ],
        }}
      />,
    );

    expect(screen.getByText("Gap check:").parentElement.textContent).toContain(
      "2 of 3 parts covered",
    );
    expect(screen.getByText("setup cost").parentElement.textContent).toContain(
      "Covered",
    );
    expect(
      screen.getByText("maintenance time").parentElement.textContent,
    ).toContain("Missing");
  });

  it("hides empty and absent gap data", () => {
    const { rerender } = render(<GapCheck gap={null} />);
    expect(screen.queryByLabelText("Question gap check")).toBeNull();
    rerender(<GapCheck gap={{ covered: 0, total: 0, parts: [] }} />);
    expect(screen.queryByLabelText("Question gap check")).toBeNull();
  });
});
