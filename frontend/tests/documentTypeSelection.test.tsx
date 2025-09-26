import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import type { ReactNode } from "react";

import { DocumentTypeProvider } from "../src/app/document-types/DocumentTypeContext";
import { useDocumentTypeSelection } from "../src/app/document-types/useDocumentTypeSelection";

describe("useDocumentTypeSelection", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  const wrapper = ({ children }: { children: ReactNode }) => (
    <DocumentTypeProvider>{children}</DocumentTypeProvider>
  );

  it("selects the first available document type by default", () => {
    const { result } = renderHook(
      ({ configs }) => useDocumentTypeSelection("workspace-1", configs),
      {
        initialProps: {
          configs: [
            { document_type: "invoice" },
            { document_type: "receipt" },
          ],
        },
        wrapper,
      },
    );

    expect(result.current.documentType).toBe("invoice");
    expect(window.localStorage.getItem("ade.documentType.workspace-1")).toBe(
      "invoice",
    );
  });

  it("persists manual changes", () => {
    const { result } = renderHook(
      ({ configs }) => useDocumentTypeSelection("workspace-1", configs),
      {
        initialProps: {
          configs: [
            { document_type: "invoice" },
            { document_type: "receipt" },
          ],
        },
        wrapper,
      },
    );

    act(() => {
      result.current.setDocumentType("receipt");
    });

    expect(result.current.documentType).toBe("receipt");
    expect(window.localStorage.getItem("ade.documentType.workspace-1")).toBe(
      "receipt",
    );
  });

  it("resets to available options when configurations change", () => {
    const { result, rerender } = renderHook(
      ({ configs }) => useDocumentTypeSelection("workspace-1", configs),
      {
        initialProps: {
          configs: [
            { document_type: "invoice" },
            { document_type: "receipt" },
          ],
        },
        wrapper,
      },
    );

    act(() => {
      result.current.setDocumentType("receipt");
    });

    rerender({ configs: [{ document_type: "contract" }] });

    expect(result.current.documentType).toBe("contract");
  });
});
