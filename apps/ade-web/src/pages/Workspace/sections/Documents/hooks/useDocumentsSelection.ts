import { useCallback, useEffect, useMemo } from "react";
import { parseAsArrayOf, parseAsString, parseAsStringEnum, useQueryState } from "nuqs";

const DOCUMENT_PANES = ["preview", "comments"] as const;

type DocumentPane = (typeof DOCUMENT_PANES)[number];

const docIdOptions = {
  history: "replace" as const,
  shallow: true,
  clearOnDefault: true,
};

const panesOptions = {
  history: "replace" as const,
  shallow: true,
  clearOnDefault: true,
};

export function useDocumentsSelection() {
  const [docId, setDocId] = useQueryState(
    "docId",
    parseAsString.withOptions(docIdOptions),
  );
  const [legacyPreviewDocId, setLegacyPreviewDocId] = useQueryState(
    "previewDocId",
    parseAsString.withOptions(docIdOptions),
  );
  const [legacyPreviewTab, setLegacyPreviewTab] = useQueryState(
    "previewTab",
    parseAsStringEnum(DOCUMENT_PANES)
      .withDefault("preview")
      .withOptions(panesOptions),
  );
  const [rawPanes, setRawPanes] = useQueryState(
    "panes",
    parseAsArrayOf(parseAsStringEnum(DOCUMENT_PANES), ",")
      .withDefault([])
      .withOptions(panesOptions),
  );

  const panes = useMemo<DocumentPane[]>(() => {
    const values = Array.isArray(rawPanes) ? rawPanes : [];
    const filtered = values.filter((pane): pane is DocumentPane =>
      DOCUMENT_PANES.includes(pane as DocumentPane),
    );
    return Array.from(new Set(filtered));
  }, [rawPanes]);

  const setPanes = useCallback(
    (nextPanes: DocumentPane[]) => {
      const unique = Array.from(new Set(nextPanes));
      if (!unique.length) {
        setRawPanes(null);
        setDocId(null);
        return;
      }
      setRawPanes(unique);
    },
    [setDocId, setRawPanes],
  );

  const openPreview = useCallback(
    (documentId: string) => {
      setDocId(documentId);
      if (!panes.includes("preview")) {
        setPanes([...panes, "preview"]);
      }
    },
    [panes, setDocId, setPanes],
  );

  const openComments = useCallback(
    (documentId: string) => {
      setDocId(documentId);
      if (!panes.includes("comments")) {
        setPanes([...panes, "comments"]);
      }
    },
    [panes, setDocId, setPanes],
  );

  const closePreview = useCallback(() => {
    setPanes(panes.filter((pane) => pane !== "preview"));
  }, [panes, setPanes]);

  const closeComments = useCallback(() => {
    setPanes(panes.filter((pane) => pane !== "comments"));
  }, [panes, setPanes]);

  useEffect(() => {
    if (!docId && panes.length) {
      setPanes([]);
    }
  }, [docId, panes, setPanes]);

  useEffect(() => {
    if (!legacyPreviewDocId) return;
    if (!docId) {
      const nextPanes =
        legacyPreviewTab === "comments" ? ["comments"] : ["preview"];
      setDocId(legacyPreviewDocId);
      setPanes(nextPanes);
    }
    setLegacyPreviewDocId(null);
    setLegacyPreviewTab(null);
  }, [
    docId,
    legacyPreviewDocId,
    legacyPreviewTab,
    setDocId,
    setLegacyPreviewDocId,
    setLegacyPreviewTab,
    setPanes,
  ]);

  return {
    docId,
    panes,
    isPreviewOpen: panes.includes("preview"),
    isCommentsOpen: panes.includes("comments"),
    setDocId,
    setPanes,
    openPreview,
    openComments,
    closePreview,
    closeComments,
  };
}
