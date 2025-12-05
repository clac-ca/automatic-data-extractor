import { useEffect, useMemo } from "react";

import { useLocation, useNavigate } from "@app/nav/history";
import { PageState } from "@ui/PageState";
import { useWorkspaceContext } from "@features/Workspace/context/WorkspaceContext";
import { SettingsLayout } from "./components/SettingsLayout";
import { SettingsSectionProvider } from "./sectionContext";
import {
  buildSettingsNav,
  defaultSettingsSection,
  resolveSectionByPath,
  workspaceSettingsSections,
} from "./settingsNav";

interface WorkspaceSettingsRouteProps {
  readonly sectionSegments?: readonly string[];
}

export default function WorkspaceSettingsRoute({ sectionSegments = [] }: WorkspaceSettingsRouteProps) {
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
  const activeGroupLabel = navGroups.find((group) => group.items.some((item) => item.id === activeSection.id))?.label;
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
    <SettingsLayout
      workspaceName={workspace.name}
      navGroups={navGroups}
      activeSectionId={activeSection.id}
      activeSectionLabel={activeSection.label}
      activeSectionDescription={activeSection.description}
      activeGroupLabel={activeGroupLabel ?? "Settings"}
    >
      <SettingsSectionProvider value={{ sectionId: activeSection.id, params: sectionParams }}>{content}</SettingsSectionProvider>
    </SettingsLayout>
  );
}

function normalizeSectionSegments(
  sectionSegments: readonly string[],
  workspaceId: string,
  search: string,
  hash: string,
) {
  const legacyMap: Record<string, string> = {
    members: "access/members",
    roles: "access/roles",
    danger: "lifecycle/danger",
  };

  const initialSegments = sectionSegments.length > 0 ? [...sectionSegments] : defaultSettingsSection.path.split("/");
  const mappedFirst = legacyMap[initialSegments[0]];
  const effectiveSegments = mappedFirst ? [...mappedFirst.split("/"), ...initialSegments.slice(1)] : initialSegments;

  const joined = effectiveSegments.join("/");
  const target =
    mappedFirst && joined
      ? `/workspaces/${workspaceId}/settings/${joined}${search}${hash}`
      : undefined;
  const needsDefaultRedirect = sectionSegments.length === 0;
  const isKnownPath =
    workspaceSettingsSections.some((section) => joined === section.path || joined.startsWith(`${section.path}/`)) ||
    mappedFirst !== undefined;
  const fallback = `/workspaces/${workspaceId}/settings/${defaultSettingsSection.path}${search}${hash}`;

  return {
    effectiveSegments: isKnownPath ? effectiveSegments : defaultSettingsSection.path.split("/"),
    redirectTo: needsDefaultRedirect || !isKnownPath || mappedFirst ? target ?? fallback : null,
  };
}
