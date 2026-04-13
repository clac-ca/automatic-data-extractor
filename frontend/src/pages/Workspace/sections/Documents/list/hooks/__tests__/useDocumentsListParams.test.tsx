import { beforeEach, describe, expect, it } from "vitest";

import { render, screen } from "@/test/test-utils";

import { useDocumentsListParams } from "../useDocumentsListParams";

function ParamsHarness({ defaultPerPage }: { readonly defaultPerPage: number }) {
  const { perPage } = useDocumentsListParams({
    currentUserId: "user-1",
    defaultPerPage,
  });

  return <div data-testid="per-page">{perPage}</div>;
}

describe("useDocumentsListParams", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("uses the provided default page size when the URL does not specify perPage", () => {
    render(<ParamsHarness defaultPerPage={500} />, {
      route: "/workspaces/ws-1/documents",
    });

    expect(screen.getByTestId("per-page")).toHaveTextContent("500");
  });

  it("prefers an explicit perPage query param over the provided default", () => {
    render(<ParamsHarness defaultPerPage={100} />, {
      route: "/workspaces/ws-1/documents?perPage=1000",
    });

    expect(screen.getByTestId("per-page")).toHaveTextContent("1000");
  });
});
