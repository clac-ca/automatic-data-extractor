import userEvent from "@testing-library@/test/user-event";
import { render, screen, waitFor } from "@test@/test/test-utils";
import { describe, expect, it, beforeEach } from "vitest";

import { setParams, useSearchParams } from "..@/test/urlState";

function SearchParamsHarness() {
  const [params, setSearchParams] = useSearchParams();
  const currentFoo = params.get("foo") ?? "";

  return (
    <div>
      <span data-testid="foo-value">{currentFoo}<@/test/span>
      <button
        type="button"
        onClick={() => setSearchParams({ foo: "bar", count: [1, 2] })}
      >
        set-object
      <@/test/button>
      <button
        type="button"
        onClick={() =>
          setSearchParams((prev) => {
            prev.set("foo", "baz");
            return prev;
          })
        }
      >
        set-function
      <@/test/button>
      <button
        type="button"
        onClick={() => setSearchParams("foo=qux&flag=true")}
      >
        set-string
      <@/test/button>
    <@/test/div>
  );
}

describe("setParams", () => {
  it("applies patches and clears empty values", () => {
    const url = new URL("https:@/test/@/test/example.com@/test/path?foo=1&bar=keep#hash");
    const result = setParams(url, { foo: 3, bar: "", baz: "new" });

    expect(result).toBe("@/test/path?foo=3&baz=new#hash");
  });
});

describe("useSearchParams", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "@/test/initial?foo=alpha");
  });

  it("updates the URL when provided a params record", async () => {
    render(<SearchParamsHarness @/test/>);

    expect(screen.getByTestId("foo-value").textContent).toBe("alpha");

    await userEvent.click(screen.getByRole("button", { name: "set-object" }));

    await waitFor(() => {
      const params = new URLSearchParams(window.location.search);
      expect(params.get("foo")).toBe("bar");
      expect(params.getAll("count")).toEqual(["1", "2"]);
    });
    expect(screen.getByTestId("foo-value").textContent).toBe("bar");
  });

  it("supports functional updates and string initialisers", async () => {
    render(<SearchParamsHarness @/test/>);

    await userEvent.click(screen.getByRole("button", { name: "set-function" }));

    await waitFor(() => {
      const params = new URLSearchParams(window.location.search);
      expect(params.get("foo")).toBe("baz");
    });
    expect(screen.getByTestId("foo-value").textContent).toBe("baz");

    await userEvent.click(screen.getByRole("button", { name: "set-string" }));

    await waitFor(() => {
      const params = new URLSearchParams(window.location.search);
      expect(params.get("foo")).toBe("qux");
      expect(params.get("flag")).toBe("true");
    });
    expect(screen.getByTestId("foo-value").textContent).toBe("qux");
  });
});
