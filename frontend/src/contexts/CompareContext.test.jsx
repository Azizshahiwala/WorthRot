import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { CompareProvider, useCompare } from "./CompareContext.jsx";

function CompareHarness() {
  const { urls, setUrl, addUrl, removeUrl } = useCompare();
  return (
    <div>
      <output data-testid="urls">{JSON.stringify(urls)}</output>
      <button onClick={addUrl}>Add URL</button>
      <button onClick={() => removeUrl(0)}>Remove first</button>
      <button onClick={() => setUrl(0, "https://youtu.be/abcdefghijk")}>
        Set first
      </button>
    </div>
  );
}

function renderCompare() {
  return render(
    <CompareProvider>
      <CompareHarness />
    </CompareProvider>,
  );
}

describe("CompareContext", () => {
  afterEach(cleanup);

  it("throws if used outside its provider", () => {
    function OutsideProvider() {
      useCompare();
      return null;
    }

    expect(() => render(<OutsideProvider />)).toThrow(
      "useCompare must be used within a CompareProvider.",
    );
  });

  it("enforces the two-to-three URL bounds", () => {
    renderCompare();

    expect(JSON.parse(screen.getByTestId("urls").textContent)).toHaveLength(2);
    fireEvent.click(screen.getByText("Remove first"));
    expect(JSON.parse(screen.getByTestId("urls").textContent)).toHaveLength(2);

    fireEvent.click(screen.getByText("Add URL"));
    fireEvent.click(screen.getByText("Add URL"));
    expect(JSON.parse(screen.getByTestId("urls").textContent)).toHaveLength(3);

    fireEvent.click(screen.getByText("Remove first"));
    expect(JSON.parse(screen.getByTestId("urls").textContent)).toHaveLength(2);
  });

  it("updates a URL at its selected index", () => {
    renderCompare();
    fireEvent.click(screen.getByText("Set first"));

    expect(JSON.parse(screen.getByTestId("urls").textContent)[0]).toBe(
      "https://youtu.be/abcdefghijk",
    );
  });
});
