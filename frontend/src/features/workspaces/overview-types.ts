export interface WorkspaceOverviewDocument {
  readonly id: string;
  readonly filename: string;
  readonly createdAt: string;
  readonly byteSize: number;
  readonly contentType: string | null;
}

export interface WorkspaceOverviewJob {
  readonly id: string;
  readonly name: string;
  readonly status: string;
  readonly startedAt: string;
}

export interface WorkspaceOverviewConfiguration {
  readonly activeConfiguration: string;
  readonly updatedAt: string;
}

export interface WorkspaceOverview {
  readonly workspace: {
    readonly id: string;
    readonly name: string;
  };
  readonly recentDocuments: WorkspaceOverviewDocument[];
  readonly activeJobs: WorkspaceOverviewJob[];
  readonly configuration: WorkspaceOverviewConfiguration;
}
