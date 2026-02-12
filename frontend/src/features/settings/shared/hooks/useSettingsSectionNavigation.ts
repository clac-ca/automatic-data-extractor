import { useCallback, useEffect, useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import type { SettingsSectionSpec } from "../types";

function parseHashSectionId(hash: string) {
  const value = hash.startsWith("#") ? hash.slice(1) : hash;
  if (!value) {
    return "";
  }
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function findSectionById(sections: readonly SettingsSectionSpec[], sectionId: string) {
  return sections.find((section) => section.id === sectionId) ?? null;
}

export function useSettingsSectionNavigation({
  sections,
  defaultSectionId,
}: {
  readonly sections: readonly SettingsSectionSpec[];
  readonly defaultSectionId?: string;
}) {
  const location = useLocation();
  const navigate = useNavigate();

  const visibleSections = useMemo(
    () => sections.filter((section) => section.visible !== false),
    [sections],
  );

  const activeSectionId = useMemo(() => {
    const hashSectionId = parseHashSectionId(location.hash);
    if (hashSectionId && findSectionById(visibleSections, hashSectionId)) {
      return hashSectionId;
    }
    if (defaultSectionId && findSectionById(visibleSections, defaultSectionId)) {
      return defaultSectionId;
    }
    return visibleSections[0]?.id ?? null;
  }, [defaultSectionId, location.hash, visibleSections]);

  const setActiveSection = useCallback(
    (sectionId: string) => {
      if (!findSectionById(visibleSections, sectionId)) {
        return;
      }

      const nextHash = `#${encodeURIComponent(sectionId)}`;
      if (location.hash === nextHash) {
        return;
      }

      navigate(
        {
          pathname: location.pathname,
          search: location.search,
          hash: nextHash,
        },
        { replace: true },
      );
    },
    [location.hash, location.pathname, location.search, navigate, visibleSections],
  );

  useEffect(() => {
    if (!activeSectionId) {
      return;
    }

    const currentHash = parseHashSectionId(location.hash);
    if (currentHash === activeSectionId) {
      return;
    }

    navigate(
      {
        pathname: location.pathname,
        search: location.search,
        hash: `#${encodeURIComponent(activeSectionId)}`,
      },
      { replace: true },
    );
  }, [activeSectionId, location.hash, location.pathname, location.search, navigate]);

  useEffect(() => {
    if (!activeSectionId) {
      return;
    }

    const rafId = window.requestAnimationFrame(() => {
      const section = document.getElementById(activeSectionId);
      if (!section) {
        return;
      }
      section.scrollIntoView({ behavior: "smooth", block: "start" });
      section.focus({ preventScroll: true });
    });

    return () => window.cancelAnimationFrame(rafId);
  }, [activeSectionId, location.pathname]);

  return {
    sections: visibleSections,
    activeSectionId,
    setActiveSection,
  };
}
