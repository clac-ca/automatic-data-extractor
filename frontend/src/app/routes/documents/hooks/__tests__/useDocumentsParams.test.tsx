import { act, renderHook } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders } from "../../../../AppProviders";
import {
  parseDocumentsSearchParams,
  serialiseDocumentsSearchParams,
  useDocumentsParams,
} from "../useDocumentsParams";

function createWrapper(initialSearch = "") {
  return function Wrapper({ children }: { readonly children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[`/workspaces/ws-1/documents${initialSearch}`]}>
        <AppProviders>{children}</AppProviders>
      </MemoryRouter>
    );
  };
}

describe("useDocumentsParams", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("omits defaults when serialising URL parameters", () => {
    const search = new URLSearchParams({ page: "1", per_page: "50", sort: "-created_at" });
    const parsed = parseDocumentsSearchParams(search);
    const serialised = serialiseDocumentsSearchParams(parsed);
    expect(serialised.toString()).toBe("");
  });

  it("resets the page when filters change", () => {
    const wrapper = createWrapper("?page=3");
    const { result } = renderHook(() => useDocumentsParams(), { wrapper });

    act(() => {
      result.current.setStatuses(["processed"]);
    });

    expect(result.current.urlState.page).toBe(1);
    expect(result.current.urlState.status).toEqual(["processed"]);
  });

  it("normalises uploader=me for API params", () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useDocumentsParams(), { wrapper });

    act(() => {
      result.current.setUploader("me");
    });

    expect(result.current.apiParams.uploader).toBe("me");
  });

  it("debounces search input before updating API params", () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useDocumentsParams(), { wrapper });

    act(() => {
      result.current.setSearch("quarterly");
    });

    expect(result.current.apiParams.q).toBeUndefined();

    act(() => {
      vi.advanceTimersByTime(320);
    });

    expect(result.current.apiParams.q).toBe("quarterly");
  });

  it("deduplicates tags and exposes them for API calls", () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useDocumentsParams(), { wrapper });

    act(() => {
      result.current.addTag("finance");
    });
    expect(result.current.urlState.tags).toEqual(["finance"]);

    act(() => {
      result.current.addTag("finance");
    });

    act(() => {
      result.current.addTag("ops");
    });

    expect(result.current.urlState.tags).toEqual(["finance", "ops"]);
    expect(result.current.apiParams.tag).toEqual(["finance", "ops"]);
  });
});
