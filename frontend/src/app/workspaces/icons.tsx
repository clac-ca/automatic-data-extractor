import type { SVGProps } from "react";

interface IconProps extends SVGProps<SVGSVGElement> {
  readonly title?: string;
}

function createIcon(path: string) {
  return function Icon({ title, ...props }: IconProps) {
    return (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden={title ? undefined : true}
        role={title ? "img" : "presentation"}
        {...props}
      >
        {title ? <title>{title}</title> : null}
        <path d={path} />
      </svg>
    );
  };
}

export const DocumentsIcon = createIcon(
  "M7 3h7l7 7v11a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2ZM14 3v5a1 1 0 0 0 1 1h5",
);

export const JobsIcon = createIcon(
  "M21 12a9 9 0 1 1-9-9m0 9 3.5 3.5M17 3v4m0 0h4M7 21v-4m0 0H3",
);

export const ConfigurationsIcon = createIcon(
  "M4 7h16M4 12h16M4 17h16m-11-8v-3m5 3v6m0 3v3m-5-6v9",
);

export const MembersIcon = createIcon(
  "M8 7a4 4 0 1 1 8 0 4 4 0 0 1-8 0Zm-4 13a6 6 0 0 1 12 0H4Zm12 0c0-1.9.9-3.6 2.2-4.7",
);

export const SettingsIcon = createIcon(
  "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm7.4-3a1 1 0 0 0 .1-.4 1 1 0 0 0-.1-.4l2-1.6a1 1 0 0 0 .2-1.3l-1.9-3.2a1 1 0 0 0-1.2-.4l-2.3.9a7 7 0 0 0-1.3-.8l-.4-2.4A1 1 0 0 0 13.5 1h-3a1 1 0 0 0-1 .9l-.4 2.4a7 7 0 0 0-1.3.8l-2.3-.9a1 1 0 0 0-1.2.4L2.4 7.8a1 1 0 0 0 .2 1.3l2 1.5a3 3 0 0 0 0 .8l-2 1.6a1 1 0 0 0-.2 1.3l1.9 3.2a1 1 0 0 0 1.2.4l2.3-.9a7 7 0 0 0 1.3.8l.4 2.4a1 1 0 0 0 1 .9h3a1 1 0 0 0 1-.9l.4-2.4a7 7 0 0 0 1.3-.8l2.3.9a1 1 0 0 0 1.2-.4l1.9-3.1a1 1 0 0 0-.2-1.3l-2-1.7Z",
);

export const DirectoryIcon = createIcon(
  "M4 10.5 12 4l8 6.5V19a1 1 0 0 1-1 1h-4v-5h-6v5H5a1 1 0 0 1-1-1v-8.5Z",
);

export const RecentIcon = createIcon(
  "M12 5v5l3 3m6-3a9 9 0 1 1-9-9",
);

export const PinIcon = createIcon(
  "M6 3h12l-4 5v4.5l2 2V16H8v-1.5l2-2V8L6 3Zm6 18v-4",
);

export const ArchiveIcon = createIcon(
  "M4 7h16v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7Zm1-4h14a2 2 0 0 1 2 2v2H3V5a2 2 0 0 1 2-2Zm5 8h4",
);
