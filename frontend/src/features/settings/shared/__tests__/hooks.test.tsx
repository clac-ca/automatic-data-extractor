import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { useSettingsErrorSummary } from "../hooks/useSettingsErrorSummary";
import { useSettingsListState } from "../hooks/useSettingsListState";
import { useSettingsMutationController } from "../hooks/useSettingsMutationController";
import { useSettingsSectionNavigation } from "../hooks/useSettingsSectionNavigation";

function createSearchWrapper(initialEntry: string) {
  return function Wrapper({ children }: { readonly children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/settings/organization/users" element={<>{children}</>} />
        </Routes>
      </MemoryRouter>
    );
  };
}

function createSectionWrapper(initialEntry: string) {
  return function Wrapper({ children }: { readonly children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route
            path="/settings/organization/users/:userId"
            element={
              <>
                <section id="profile" />
                <section id="roles" />
                {children}
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    );
  };
}

describe("useSettingsListState", () => {
  it("reads defaults from URL and updates search while resetting page", () => {
    const wrapper = createSearchWrapper(
      "/settings/organization/users?q=alex&page=3&pageSize=50&status=active",
    );

    const { result } = renderHook(
      () => useSettingsListState({ defaults: { sort: "createdAt", order: "desc" }, filterKeys: ["status"] }),
      { wrapper },
    );

    expect(result.current.state.q).toBe("alex");
    expect(result.current.state.page).toBe(3);
    expect(result.current.state.pageSize).toBe(50);
    expect(result.current.state.sort).toBe("createdAt");
    expect(result.current.state.order).toBe("desc");
    expect(result.current.state.filters.status).toBe("active");

    act(() => {
      result.current.setQuery("jordan");
    });

    expect(result.current.state.q).toBe("jordan");
    expect(result.current.state.page).toBe(1);
    expect(result.current.withCurrentSearch("/settings/organization/users/create")).toContain("q=jordan");
    expect(result.current.withCurrentSearch("/settings/organization/users/create")).not.toContain("page=");
  });

  it("updates and clears filter values", () => {
    const wrapper = createSearchWrapper("/settings/organization/users");
    const { result } = renderHook(
      () => useSettingsListState({ filterKeys: ["status", "type"] }),
      { wrapper },
    );

    act(() => {
      result.current.setFilter("status", "inactive");
    });

    act(() => {
      result.current.setFilter("type", "external");
    });

    expect(result.current.state.filters).toEqual({ status: "inactive", type: "external" });

    act(() => {
      result.current.clearFilters();
    });

    expect(result.current.state.filters).toEqual({});
  });
});

describe("useSettingsMutationController", () => {
  it("tracks pending, success, and error states", async () => {
    const { result } = renderHook(() => useSettingsMutationController());

    await act(async () => {
      await result.current.run(async () => "ok", {
        pendingMessage: "Saving",
        successMessage: "Saved",
      });
    });

    expect(result.current.state).toEqual({ status: "success", message: "Saved" });

    await act(async () => {
      try {
        await result.current.run(
          async () => {
            throw new Error("boom");
          },
          {
            successMessage: "Saved",
            getErrorMessage: () => "Unable to save",
          },
        );
      } catch {
        // expected
      }
    });

    expect(result.current.state).toEqual({ status: "error", message: "Unable to save" });
  });
});

describe("useSettingsErrorSummary", () => {
  it("builds summary and field lookups", () => {
    const { result } = renderHook(() =>
      useSettingsErrorSummary({
        fieldIdByKey: {
          email: "user-email",
          displayName: "user-display-name",
        },
        fieldLabelByKey: {
          email: "Email",
          displayName: "Display name",
        },
      }),
    );

    act(() => {
      result.current.setClientErrors({
        email: "Email is required.",
      });
    });

    expect(result.current.summary?.items).toHaveLength(1);
    expect(result.current.summary?.items[0]).toMatchObject({
      label: "Email",
      fieldId: "user-email",
      message: "Email is required.",
    });

    act(() => {
      result.current.setProblemErrors({
        displayName: ["Display name is too long"],
      });
    });

    expect(result.current.getFieldError("displayName")).toBe("Display name is too long");
  });
});

describe("useSettingsSectionNavigation", () => {
  it("derives active section from hash and updates hash through setter", async () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    const wrapper = createSectionWrapper("/settings/organization/users/user-1#roles");

    const { result } = renderHook(
      () =>
        useSettingsSectionNavigation({
          sections: [
            { id: "profile", label: "Profile" },
            { id: "roles", label: "Roles" },
          ],
          defaultSectionId: "profile",
        }),
      { wrapper },
    );

    expect(result.current.activeSectionId).toBe("roles");

    act(() => {
      result.current.setActiveSection("profile");
    });

    await waitFor(() => {
      expect(result.current.activeSectionId).toBe("profile");
    });
  });

  it("falls back to default section when hash is invalid", () => {
    const wrapper = createSectionWrapper("/settings/organization/users/user-1#unknown");

    const { result } = renderHook(
      () =>
        useSettingsSectionNavigation({
          sections: [
            { id: "profile", label: "Profile" },
            { id: "roles", label: "Roles" },
          ],
          defaultSectionId: "profile",
        }),
      { wrapper },
    );

    expect(result.current.activeSectionId).toBe("profile");
  });
});
