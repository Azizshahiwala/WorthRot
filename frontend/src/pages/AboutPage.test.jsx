import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { tabs } from "../config/tabs.js";
import AboutPage from "./AboutPage.jsx";

describe("AboutPage", () => {
  afterEach(cleanup);

  it("renders the static product information and enables its tab", () => {
    render(<AboutPage />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Is this video worth your time?",
      }),
    ).toBeTruthy();
    expect(screen.getAllByRole("list")).toHaveLength(3);
    expect(tabs.find((tab) => tab.path === "/about").enabled).toBe(true);
    expect(screen.queryByRole("heading", { name: "Author" })).toBeNull();
  });
});
