import type { ConfigurationRecord } from "@api/configurations";
import type { WorkspaceProfile } from "@api/workspaces";

export interface WorkspaceQueryResult {
  readonly workspaces: WorkspaceProfile[];
  readonly defaultWorkspaceId: string | null;
}

export interface DocumentTypeOption {
  readonly id: string;
  readonly label: string;
  readonly isActive: boolean;
}

export function mapConfigurationsToDocumentTypes(
  configurations: ConfigurationRecord[]
): DocumentTypeOption[] {
  const grouped = new Map<string, DocumentTypeOption>();

  configurations.forEach((config) => {
    const existing = grouped.get(config.documentType);
    const label = config.documentType;
    const option: DocumentTypeOption = {
      id: config.documentType,
      label,
      isActive: config.isActive
    };

    if (!existing) {
      grouped.set(config.documentType, option);
    } else if (!existing.isActive && config.isActive) {
      grouped.set(config.documentType, option);
    }
  });

  return Array.from(grouped.values()).sort((a, b) => a.label.localeCompare(b.label));
}
