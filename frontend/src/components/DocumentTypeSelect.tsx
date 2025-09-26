import { useMemo } from "react";

import { useActiveConfigurationsQuery } from "../app/documents/hooks";
import { useDocumentTypeSelection } from "../app/document-types/useDocumentTypeSelection";
import { useWorkspaceSelection } from "../app/workspaces/WorkspaceSelectionContext";
import { describeConfiguration } from "../api/configurations";

export function DocumentTypeSelect() {
  const { selectedWorkspaceId } = useWorkspaceSelection();
  const { data: configurations = [], isLoading } = useActiveConfigurationsQuery(
    selectedWorkspaceId,
  );

  const { documentType, documentTypes, setDocumentType } =
    useDocumentTypeSelection(selectedWorkspaceId, configurations);

  const optionsByType = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const configuration of configurations) {
      const label = describeConfiguration(configuration);
      const items = map.get(configuration.document_type) ?? [];
      items.push(label);
      map.set(configuration.document_type, items);
    }
    return map;
  }, [configurations]);

  if (!selectedWorkspaceId) {
    return null;
  }

  return (
    <label className="document-type-select">
      <span className="muted">Document type</span>
      <select
        className="document-type-field"
        value={documentType ?? ""}
        onChange={(event) => setDocumentType(event.target.value || null)}
        disabled={isLoading || documentTypes.length === 0}
      >
        <option value="" disabled>
          {isLoading ? "Loading…" : "Select document type"}
        </option>
        {documentTypes.map((type) => (
          <option key={type} value={type}>
            {type}
            {optionsByType.get(type)?.length
              ? ` (${optionsByType.get(type)?.length ?? 0})`
              : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
