import { useEffect, useMemo } from "react";

import { useLocation, useNavigate } from "react-router-dom";
import { PageState } from "@components/layouts/page-state";
import { useWorkspaceContext } from "@pages/Workspace/context/WorkspaceContext";
import { SettingsShell } from "./components/SettingsShell";
import { SettingsSectionProvider } from "./sectionContext";
import {
  buildSettingsNav,
  defaultSettingsSection,
  resolveSectionByPath,
  workspaceSettingsSections,
} from "./settingsNav";

interface WorkspaceSettingsScreenProps {
  readonly sectionSegments?: readonly string[];
}

export default function WorkspaceSettingsScreen({ sectionSegments = [] }: WorkspaceSettingsScreenProps) {
  const { workspace, hasPermission } = useWorkspaceContext();
  const navigate = useNavigate();
  const location = useLocation();

  const { effectiveSegments, redirectTo } = useMemo(
    () => normalizeSectionSegments(sectionSegments, workspace.id, location.search, location.hash),
    [sectionSegments, workspace.id, location.search, location.hash],
  );
  const activeSection = resolveSectionByPath(effectiveSegments) ?? defaultSettingsSection;

  useEffect(() => {
    if (redirectTo) {
      navigate(redirectTo, { replace: true });
    }
  }, [redirectTo, navigate]);
  const sectionParams = useMemo(() => {
    const baseSegments = activeSection.path.split("/");
    return effectiveSegments.slice(baseSegments.length);
  }, [activeSection.path, effectiveSegments]);

  const navGroups = useMemo(() => buildSettingsNav(workspace.id, hasPermission), [workspace.id, hasPermission]);
  const flatNavItems = navGroups.flatMap((group) => group.items);
  const activeNavItem = flatNavItems.find((item) => item.id === activeSection.id);
  const isRestricted = activeNavItem?.disabled;

  const content = isRestricted ? (
    <PageState
      title="You don't have access to this section"
      description="You need additional permissions to manage this area of workspace settings."
      variant="error"
    />
  ) : (
    activeSection.element
  );

  return (
    <SettingsShell
      workspaceName={workspace.name}
      navGroups={navGroups}
      activeSectionId={activeSection.id}
      activeSectionLabel={activeSection.label}
      activeSectionDescription={activeSection.description}
    >
      <SettingsSectionProvider value={{ sectionId: activeSection.id, params: sectionParams }}>{content}</SettingsSectionProvider>
    </SettingsShell>
  );
}

function normalizeSectionSegments(
  sectionSegments: readonly string[],
  workspaceId: string,
  search: string,
  hash: string,
) {
  const initialSegments = sectionSegments.length > 0 ? [...sectionSegments] : defaultSettingsSection.path.split("/");
  const effectiveSegments = initialSegments;
  const joined = effectiveSegments.join("/");
  const needsDefaultRedirect = sectionSegments.length === 0;
  const isKnownPath = workspaceSettingsSections.some(
    (section) => joined === section.path || joined.startsWith(`${section.path}/`),
  );
  const fallback = `/workspaces/${workspaceId}/settings/${defaultSettingsSection.path}${search}${hash}`;

  return {
    effectiveSegments: isKnownPath ? effectiveSegments : defaultSettingsSection.path.split("/"),
    redirectTo: needsDefaultRedirect || !isKnownPath ? fallback : null,
  };
}
