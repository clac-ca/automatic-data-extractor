import userEvent from "@testing-library/user-event";
import { render, screen, waitFor } from "@test/test-utils";
import { describe, expect, it, beforeEach } from "vitest";

import {
  DEFAULT_CONFIG_BUILDER_SEARCH,
  mergeConfigBuilderSearch,
  readConfigBuilderSearch,
  setParams,
  useSearchParams,
} from "../urlState";

function SearchParamsHarness() {
  const [params, setSearchParams] = useSearchParams();
  const currentFoo = params.get("foo") ?? "";

  return (
    <div>
      <span data-testid="foo-value">{currentFoo}</span>
      <button
        type="button"
        onClick={() => setSearchParams({ foo: "bar", count: [1, 2] })}
      >
        set-object
      </button>
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
      </button>
      <button
        type="button"
        onClick={() => setSearchParams("foo=qux&flag=true")}
      >
        set-string
      </button>
    </div>
  );
}

describe("setParams", () => {
  it("applies patches and clears empty values", () => {
    const url = new URL("https://example.com/path?foo=1&bar=keep#hash");
    const result = setParams(url, { foo: 3, bar: "", baz: "new" });

    expect(result).toBe("/path?foo=3&baz=new#hash");
  });
});

describe("useSearchParams", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/initial?foo=alpha");
  });

  it("updates the URL when provided a params record", async () => {
    render(<SearchParamsHarness />);

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
    render(<SearchParamsHarness />);

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

describe("Config Builder search helpers", () => {
  it("parses defaults and presence flags", () => {
    const snapshot = readConfigBuilderSearch("file=/src/app.ts&view=split&console=open&pane=problems&runId=run-123");

    expect(snapshot.file).toBe("/src/app.ts");
    expect(snapshot.view).toBe("split");
    expect(snapshot.console).toBe("open");
    expect(snapshot.pane).toBe("problems");
    expect(snapshot.tab).toBe(DEFAULT_CONFIG_BUILDER_SEARCH.tab);
    expect(snapshot.runId).toBe("run-123");
    expect(snapshot.present).toEqual({
      tab: false,
      pane: true,
      console: true,
      view: true,
      file: true,
      runId: true,
    });
  });

  it("falls back to defaults when values are invalid", () => {
    const snapshot = readConfigBuilderSearch("pane=unknown&console=nope&view=side&tab=invalid");

    expect(snapshot.pane).toBe(DEFAULT_CONFIG_BUILDER_SEARCH.pane);
    expect(snapshot.console).toBe(DEFAULT_CONFIG_BUILDER_SEARCH.console);
    expect(snapshot.view).toBe(DEFAULT_CONFIG_BUILDER_SEARCH.view);
    expect(snapshot.tab).toBe(DEFAULT_CONFIG_BUILDER_SEARCH.tab);
    expect(snapshot.present.pane).toBe(true);
  });

  it("ignores legacy parameters", () => {
    const snapshot = readConfigBuilderSearch("path=/legacy/file.py&run_id=run-456&pane=console");

    expect(snapshot.file).toBeUndefined();
    expect(snapshot.runId).toBeUndefined();
    expect(snapshot.pane).toBe(DEFAULT_CONFIG_BUILDER_SEARCH.pane);
    expect(snapshot.present.file).toBe(false);
    expect(snapshot.present.runId).toBe(false);
  });

  it("captures run identifier from the canonical param", () => {
    const primary = readConfigBuilderSearch("runId=run-123");

    expect(primary.runId).toBe("run-123");
    expect(primary.present.runId).toBe(true);
  });

  it("merges patches and removes defaults", () => {
    const base = new URLSearchParams("file=/one.ts&console=open&pane=terminal&runId=run-123");
    const next = mergeConfigBuilderSearch(base, {
      file: undefined,
      pane: "problems",
      view: "zen",
      runId: undefined,
    });

    expect(next.get("console")).toBe("open");
    expect(next.get("pane")).toBe("problems");
    expect(next.get("view")).toBe("zen");
    expect(next.has("file")).toBe(false);
    expect(next.has("runId")).toBe(false);

    const reset = mergeConfigBuilderSearch(next, { view: "editor" });
    expect(reset.has("view")).toBe(false);
  });
});
