import { useEffect, useMemo } from "react";

import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useConfigureAuthenticatedTopbar } from "@/app/layouts/components/topbar/AuthenticatedTopbarContext";
import { PageState } from "@/components/layout";
import { useGlobalPermissions } from "@/hooks/auth/useGlobalPermissions";
import {
  OrganizationSettingsTopbarSearch,
  OrganizationSettingsTopbarSearchButton,
} from "./components/OrganizationSettingsTopbarSearch";
import { OrganizationSettingsShell } from "./components/OrganizationSettingsShell";
import { OrganizationSettingsSectionProvider } from "./sectionContext";
import {
  buildOrganizationSettingsNav,
  getDefaultOrganizationSettingsSection,
  getOrganizationSectionAccessState,
  organizationSettingsSections,
  resolveOrganizationSectionByPath,
} from "./settingsNav";

interface OrganizationSettingsScreenProps {
  readonly sectionSegments?: readonly string[];
}

export default function OrganizationSettingsScreen({ sectionSegments = [] }: OrganizationSettingsScreenProps) {
  const { hasPermission, canAccessOrganizationSettings } = useGlobalPermissions();
  const navigate = useNavigate();
  const location = useLocation();
  const routeParams = useParams<{ "*": string }>();
  const effectiveInputSegments = useMemo(() => {
    if (sectionSegments.length > 0) {
      return sectionSegments;
    }
    const wildcard = routeParams["*"] ?? "";
    return wildcard
      .split("/")
      .map((entry) => entry.trim())
      .filter((entry) => entry.length > 0);
  }, [routeParams, sectionSegments]);

  const defaultSection = useMemo(() => getDefaultOrganizationSettingsSection(hasPermission), [hasPermission]);
  const navGroups = useMemo(() => buildOrganizationSettingsNav(hasPermission), [hasPermission]);
  const topbarConfig = useMemo(
    () => ({
      desktopCenter: <OrganizationSettingsTopbarSearch navGroups={navGroups} className="w-full max-w-xl" />,
      mobileAction: <OrganizationSettingsTopbarSearchButton navGroups={navGroups} />,
    }),
    [navGroups],
  );

  useConfigureAuthenticatedTopbar(canAccessOrganizationSettings ? topbarConfig : null);

  const { effectiveSegments, redirectTo } = useMemo(
    () => normalizeSectionSegments(effectiveInputSegments, location.search, location.hash, defaultSection.path),
    [effectiveInputSegments, location.search, location.hash, defaultSection.path],
  );

  useEffect(() => {
    if (redirectTo) {
      navigate(redirectTo, { replace: true });
    }
  }, [navigate, redirectTo]);

  if (!canAccessOrganizationSettings) {
    return (
      <div className="mx-auto w-full max-w-6xl px-6 py-8">
        <PageState
          title="You don't have access"
          description="You need organization-level permissions to view this area."
          variant="error"
        />
      </div>
    );
  }

  const activeSection = resolveOrganizationSectionByPath(effectiveSegments) ?? defaultSection;

  const flatNavItems = navGroups.flatMap((group) => group.items);
  const activeNavItem = flatNavItems.find((item) => item.id === activeSection.id);
  const activeAccess = getOrganizationSectionAccessState(activeSection, hasPermission);
  const isRestricted = !activeAccess.canAccess || Boolean(activeNavItem?.disabled);

  const sectionParams = effectiveSegments.slice(activeSection.path.split("/").length);

  const content = isRestricted ? (
    <PageState
      title="You don't have access to this section"
      description="You need additional permissions to manage this area of organization settings."
      variant="error"
    />
  ) : (
    activeSection.element
  );

  return (
    <OrganizationSettingsShell
      navGroups={navGroups}
      activeSectionId={activeSection.id}
      activeSectionLabel={activeSection.label}
      activeSectionDescription={activeSection.description}
    >
      <OrganizationSettingsSectionProvider value={{ sectionId: activeSection.id, params: sectionParams }}>
        {content}
      </OrganizationSettingsSectionProvider>
    </OrganizationSettingsShell>
  );
}

function normalizeSectionSegments(
  sectionSegments: readonly string[],
  search: string,
  hash: string,
  defaultPath: string,
) {
  const initialSegments = sectionSegments.length > 0 ? [...sectionSegments] : defaultPath.split("/");
  const joined = initialSegments.join("/");
  const needsDefaultRedirect = sectionSegments.length === 0;
  const isKnownPath = organizationSettingsSections.some(
    (section) => joined === section.path || joined.startsWith(`${section.path}/`),
  );

  return {
    effectiveSegments: isKnownPath ? initialSegments : defaultPath.split("/"),
    redirectTo: needsDefaultRedirect || !isKnownPath ? `/organization/settings/${defaultPath}${search}${hash}` : null,
  };
}
