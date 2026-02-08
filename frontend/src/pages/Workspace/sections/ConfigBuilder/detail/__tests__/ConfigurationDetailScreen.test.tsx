import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConfigurationDetailScreen from "../index";

const navigateMock = vi.fn();

type MockConfig = {
  id: string;
  display_name: string;
  status: string;
  updated_at: string;
  activated_at?: string | null;
};

let mockConfig: MockConfig | null = {
  id: "cfg-1",
  display_name: "Config One",
  status: "draft",
  updated_at: "2026-02-07T10:00:00.000Z",
  activated_at: null,
};
let mockConfigLoading = false;
let mockConfigError = false;
let mockConfigFetchedAfterMount = true;

vi.mock("react-router-dom", () => ({
  useNavigate: () => navigateMock,
}));

vi.mock("@/pages/Workspace/context/WorkspaceContext", () => ({
  useWorkspaceContext: () => ({
    workspace: {
      id: "ws-1",
      name: "Workspace One",
    },
  }),
}));

vi.mock("@/providers/notifications", () => ({
  useNotifications: () => ({
    notifyToast: vi.fn(),
  }),
}));

vi.mock("@/pages/Workspace/hooks/configurations", () => ({
  useConfigurationQuery: () => ({
    data: mockConfig,
    isLoading: mockConfigLoading,
    isError: mockConfigError,
    isSuccess: !mockConfigLoading && !mockConfigError,
    isFetchedAfterMount: mockConfigFetchedAfterMount,
    refetch: vi.fn(),
  }),
  useConfigurationsQuery: () => ({
    data: {
      items: [
        { id: "cfg-1", display_name: "Config One", status: "active" },
        { id: "cfg-2", display_name: "Config Two", status: "draft" },
      ],
    },
    refetch: vi.fn(),
  }),
  useArchiveConfigurationMutation: () => ({
    mutate: vi.fn(),
    isPending: false,
    error: null,
    reset: vi.fn(),
  }),
  useDuplicateConfigurationMutation: () => ({
    mutate: vi.fn(),
    isPending: false,
    error: null,
    reset: vi.fn(),
  }),
}));

vi.mock("@/api/configurations/api", () => ({
  exportConfiguration: vi.fn(),
}));

describe("ConfigurationDetailScreen", () => {
  beforeEach(() => {
    navigateMock.mockReset();
    mockConfig = {
      id: "cfg-1",
      display_name: "Config One",
      status: "draft",
      updated_at: "2026-02-07T10:00:00.000Z",
      activated_at: null,
    };
    mockConfigLoading = false;
    mockConfigError = false;
    mockConfigFetchedAfterMount = true;
  });

  it("waits for a fresh configuration snapshot before rendering status-driven actions", () => {
    mockConfigFetchedAfterMount = false;
    mockConfig = {
      id: "cfg-1",
      display_name: "Config One",
      status: "draft",
      updated_at: "2026-02-07T10:00:00.000Z",
      activated_at: null,
    };

    render(<ConfigurationDetailScreen params={{ configId: "cfg-1" }} />);

    expect(screen.getByText("Refreshing configuration")).toBeInTheDocument();
  });

  it("shows read-only guidance for active configurations", () => {
    mockConfig = {
      id: "cfg-1",
      display_name: "Config One",
      status: "active",
      updated_at: "2026-02-07T10:00:00.000Z",
      activated_at: "2026-02-07T10:01:00.000Z",
    };

    render(<ConfigurationDetailScreen params={{ configId: "cfg-1" }} />);

    expect(screen.getByText("Read-only configuration")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Duplicate to edit" }).length).toBeGreaterThan(0);
  });
});
