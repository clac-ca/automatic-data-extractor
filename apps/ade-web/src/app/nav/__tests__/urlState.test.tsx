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
    const snapshot = readConfigBuilderSearch("file=/src/app.ts&view=split&console=open&pane=validation");

    expect(snapshot.file).toBe("/src/app.ts");
    expect(snapshot.view).toBe("split");
    expect(snapshot.console).toBe("open");
    expect(snapshot.pane).toBe("problems");
    expect(snapshot.tab).toBe(DEFAULT_CONFIG_BUILDER_SEARCH.tab);
    expect(snapshot.present).toEqual({
      tab: false,
      pane: true,
      console: true,
      view: true,
      file: true,
      runId: false,
    });
  });

  it("maps legacy pane names to the new set", () => {
    const snapshot = readConfigBuilderSearch("pane=problems");

    expect(snapshot.pane).toBe("problems");
  });

  it("maps legacy console pane names to terminal and summary aliases", () => {
    expect(readConfigBuilderSearch("pane=console").pane).toBe("terminal");
    expect(readConfigBuilderSearch("pane=run-summary").pane).toBe("runSummary");
  });

  it("supports legacy path parameters", () => {
    const snapshot = readConfigBuilderSearch("path=/legacy/file.py");

    expect(snapshot.file).toBe("/legacy/file.py");
    expect(snapshot.present.file).toBe(true);
    expect(snapshot.present.runId).toBe(false);
  });

  it("captures run identifiers from multiple param shapes", () => {
    const primary = readConfigBuilderSearch("runId=run-123");
    const legacy = readConfigBuilderSearch("run_id=run-456");

    expect(primary.runId).toBe("run-123");
    expect(primary.present.runId).toBe(true);
    expect(legacy.runId).toBe("run-456");
    expect(legacy.present.runId).toBe(true);
  });

  it("merges patches and removes defaults", () => {
    const base = new URLSearchParams("file=/one.ts&console=open&pane=console");
    const next = mergeConfigBuilderSearch(base, {
      file: undefined,
      pane: "problems",
      view: "zen",
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
