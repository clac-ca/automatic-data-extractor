import type { ChangeEvent } from "react";

import "@styles/form-controls.css";

import { useWorkspace } from "@hooks/useWorkspace";

import { useDocumentTypesQuery } from "@features/configurations/hooks/useDocumentTypesQuery";

export function DocumentTypeFilter(): JSX.Element {
  const { workspaceId, documentType, setDocumentType } = useWorkspace();
  const { data, isLoading } = useDocumentTypesQuery(workspaceId);
  const documentTypes = data?.documentTypes ?? [];

  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value || null;
    setDocumentType(value);
  };

  return (
    <label className="form-control">
      <span className="form-control__label">Document type</span>
      <select
        className="form-control__select"
        value={documentType ?? ""}
        onChange={handleChange}
        disabled={!workspaceId || documentTypes.length === 0 || isLoading}
      >
        <option value="">All types</option>
        {documentTypes.map((type) => (
          <option key={type.id} value={type.id}>
            {type.label}
          </option>
        ))}
      </select>
    </label>
  );
}
