import type { SVGProps } from "react";

export type IconProps = SVGProps<SVGSVGElement> & {
  readonly title?: string;
};

export function IconBase({
  title,
  children,
  viewBox = "0 0 20 20",
  fill = "none",
  stroke = "currentColor",
  strokeWidth = 1.6,
  strokeLinecap = "round",
  strokeLinejoin = "round",
  ...rest
}: IconProps) {
  const ariaLabel = rest["aria-label"];
  const ariaLabelledBy = rest["aria-labelledby"];
  const hasAccessibleLabel = Boolean(title || ariaLabel || ariaLabelledBy);
  const ariaHidden = rest["aria-hidden"] ?? (hasAccessibleLabel ? undefined : true);
  const role = rest.role ?? (hasAccessibleLabel ? "img" : "presentation");
  const focusable = rest.focusable ?? false;

  return (
    <svg
      viewBox={viewBox}
      fill={fill}
      stroke={stroke}
      strokeWidth={strokeWidth}
      strokeLinecap={strokeLinecap}
      strokeLinejoin={strokeLinejoin}
      aria-hidden={ariaHidden}
      role={role}
      focusable={focusable}
      {...rest}
    >
      {title ? <title>{title}</title> : null}
      {children}
    </svg>
  );
}

/**
 * Pro icon pack
 *
 * Primary set: Lucide (ISC License) — https://lucide.dev/license
 * IDE glyphs: VS Code Codicons (CC BY 4.0) — https://github.com/microsoft/vscode-codicons
 *
 * Notes:
 * - All Lucide-based icons are generated from lucide-static icon-nodes.json.
 * - ExplorerIcon, SourceControlIcon, and CollapseAllIcon use Codicon glyphs for VS Code parity.
 */
const ICON_24 = { viewBox: "0 0 24 24", strokeWidth: 2 };
const ICON_16 = { viewBox: "0 0 16 16", strokeWidth: 1.4 };
const ICON_10 = { viewBox: "0 0 10 10", strokeWidth: 1.5 };

export function DocumentIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
      <path d="M10 9H8" />
      <path d="M16 13H8" />
      <path d="M16 17H8" />
    </IconBase>
  );
}

export function SearchIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={11} cy={11} r={8} />
      <path d="m21 21-4.3-4.3" />
    </IconBase>
  );
}

export function UploadIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1={12} x2={12} y1={3} y2={15} />
    </IconBase>
  );
}

export function DownloadIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1={12} x2={12} y1={15} y2={3} />
    </IconBase>
  );
}

export function GridIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect x={3} y={3} width={7} height={7} rx={1} />
      <rect x={14} y={3} width={7} height={7} rx={1} />
      <rect x={14} y={14} width={7} height={7} rx={1} />
      <rect x={3} y={14} width={7} height={7} rx={1} />
    </IconBase>
  );
}

export function BoardIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect x={3} y={3} width={18} height={18} rx={2} />
      <path d="M8 7v7" />
      <path d="M12 7v4" />
      <path d="M16 7v9" />
    </IconBase>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props} strokeWidth={2.25}>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </IconBase>
  );
}

export function LinkIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M9 17H7A5 5 0 0 1 7 7h2" />
      <path d="M15 7h2a5 5 0 1 1 0 10h-2" />
      <line x1={8} x2={16} y1={12} y2={12} />
    </IconBase>
  );
}

export function TrashIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M3 6h18" />
      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
      <line x1={10} x2={10} y1={11} y2={17} />
      <line x1={14} x2={14} y1={11} y2={17} />
    </IconBase>
  );
}

export function OpenInNewIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    </IconBase>
  );
}

export function MoreIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={12} cy={12} r={1} />
      <circle cx={19} cy={12} r={1} />
      <circle cx={5} cy={12} r={1} />
    </IconBase>
  );
}

export function RefreshIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M8 16H3v5" />
    </IconBase>
  );
}

export function SettingsIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <line x1={21} x2={14} y1={4} y2={4} />
      <line x1={10} x2={3} y1={4} y2={4} />
      <line x1={21} x2={12} y1={12} y2={12} />
      <line x1={8} x2={3} y1={12} y2={12} />
      <line x1={21} x2={16} y1={20} y2={20} />
      <line x1={12} x2={3} y1={20} y2={20} />
      <line x1={14} x2={14} y1={2} y2={6} />
      <line x1={8} x2={8} y1={10} y2={14} />
      <line x1={16} x2={16} y1={18} y2={22} />
    </IconBase>
  );
}

export function ChatIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </IconBase>
  );
}

export function UserIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <circle cx={12} cy={7} r={4} />
    </IconBase>
  );
}

export function ChevronDownIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props} strokeWidth={2.25}>
      <path d="m6 9 6 6 6-6" />
    </IconBase>
  );
}

export function ChevronLeftIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props} strokeWidth={2.25}>
      <path d="m15 18-6-6 6-6" />
    </IconBase>
  );
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props} strokeWidth={2.25}>
      <path d="m9 18 6-6-6-6" />
    </IconBase>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props} strokeWidth={2.25}>
      <path d="M20 6 9 17l-5-5" />
    </IconBase>
  );
}

export function AlertTriangleIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </IconBase>
  );
}

export function ClockIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={12} cy={12} r={10} />
      <polyline points="12 6 12 12 16 14" />
    </IconBase>
  );
}

export function DirectoryIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8" />
      <path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </IconBase>
  );
}

export function MenuIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <line x1={4} x2={20} y1={12} y2={12} />
      <line x1={4} x2={20} y1={6} y2={6} />
      <line x1={4} x2={20} y1={18} y2={18} />
    </IconBase>
  );
}

export function GearIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z" />
      <path d="M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" />
      <path d="M12 2v2" />
      <path d="M12 22v-2" />
      <path d="m17 20.66-1-1.73" />
      <path d="M11 10.27 7 3.34" />
      <path d="m20.66 17-1.73-1" />
      <path d="m3.34 7 1.73 1" />
      <path d="M14 12h8" />
      <path d="M2 12h2" />
      <path d="m20.66 7-1.73 1" />
      <path d="m3.34 17 1.73-1" />
      <path d="m17 3.34-1 1.73" />
      <path d="m11 13.73-4 6.93" />
    </IconBase>
  );
}

export function PinIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 17v5" />
      <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z" />
    </IconBase>
  );
}

export function UnpinIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 17v5" />
      <path d="M15 9.34V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H7.89" />
      <path d="m2 2 20 20" />
      <path d="M9 9v1.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h11" />
    </IconBase>
  );
}

export function RunsIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M3 12h.01" />
      <path d="M3 18h.01" />
      <path d="M3 6h.01" />
      <path d="M8 12h13" />
      <path d="M8 18h13" />
      <path d="M8 6h13" />
    </IconBase>
  );
}

export function ConfigureIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M20 7h-9" />
      <path d="M14 17H5" />
      <circle cx={17} cy={17} r={3} />
      <circle cx={7} cy={7} r={3} />
    </IconBase>
  );
}

export function InfoIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={12} cy={12} r={10} opacity={0.8} />
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </IconBase>
  );
}

export function SuccessIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={12} cy={12} r={10} opacity={0.8} />
      <path d="m9 12 2 2 4-4" />
    </IconBase>
  );
}

export function WarningIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={12} cy={12} r={10} opacity={0.8} />
      <line x1={12} x2={12} y1={8} y2={12} />
      <line x1={12} x2={12.01} y1={16} y2={16} />
    </IconBase>
  );
}

export function ErrorIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={12} cy={12} r={10} opacity={0.8} />
      <path d="m15 9-6 6" />
      <path d="m9 9 6 6" />
    </IconBase>
  );
}

export function SunIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={12} cy={12} r={4} />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.93 4.93 1.41 1.41" />
      <path d="m17.66 17.66 1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m6.34 17.66-1.41 1.41" />
      <path d="m19.07 4.93-1.41 1.41" />
    </IconBase>
  );
}

export function MoonIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
    </IconBase>
  );
}

export function SystemIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect x={2} y={3} width={20} height={14} rx={2} />
      <line x1={8} x2={16} y1={21} y2={21} />
      <line x1={12} x2={12} y1={17} y2={21} />
    </IconBase>
  );
}

export function ExplorerIcon(props: IconProps) {
  return (
    // VS Code Codicon: "files"
    <IconBase {...ICON_24} {...props} stroke="none">
      <path
        d="M17.5 0h-9L7 1.5V6H2.5L1 7.5v15.07L2.5 24h12.07L16 22.57V18h4.7l1.3-1.43V4.5L17.5 0zm0 2.12l2.38 2.38H17.5V2.12zm-3 20.38h-12v-15H7v9.07L8.5 18h6v4.5zm6-6h-12v-15H16V6h4.5v10.5z"
        fill="currentColor"
      />
    </IconBase>
  );
}


export function SourceControlIcon(props: IconProps) {
  return (
    // VS Code Codicon: "source-control"
    <IconBase {...ICON_24} {...props} stroke="none">
      <path
        d="M21.007 8.222A3.738 3.738 0 0 0 15.045 5.2a3.737 3.737 0 0 0 1.156 6.583 2.988 2.988 0 0 1-2.668 1.67h-2.99a4.456 4.456 0 0 0-2.989 1.165V7.4a3.737 3.737 0 1 0-1.494 0v9.117a3.776 3.776 0 1 0 1.816.099 2.99 2.99 0 0 1 2.668-1.667h2.99a4.484 4.484 0 0 0 4.223-3.039 3.736 3.736 0 0 0 3.25-3.687zM4.565 3.738a2.242 2.242 0 1 1 4.484 0 2.242 2.242 0 0 1-4.484 0zm4.484 16.441a2.242 2.242 0 1 1-4.484 0 2.242 2.242 0 0 1 4.484 0zm8.221-9.715a2.242 2.242 0 1 1 0-4.485 2.242 2.242 0 0 1 0 4.485z"
        fill="currentColor"
      />
    </IconBase>
  );
}


export function ExtensionsIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M15.39 4.39a1 1 0 0 0 1.68-.474 2.5 2.5 0 1 1 3.014 3.015 1 1 0 0 0-.474 1.68l1.683 1.682a2.414 2.414 0 0 1 0 3.414L19.61 15.39a1 1 0 0 1-1.68-.474 2.5 2.5 0 1 0-3.014 3.015 1 1 0 0 1 .474 1.68l-1.683 1.682a2.414 2.414 0 0 1-3.414 0L8.61 19.61a1 1 0 0 0-1.68.474 2.5 2.5 0 1 1-3.014-3.015 1 1 0 0 0 .474-1.68l-1.683-1.682a2.414 2.414 0 0 1 0-3.414L4.39 8.61a1 1 0 0 1 1.68.474 2.5 2.5 0 1 0 3.014-3.015 1 1 0 0 1-.474-1.68l1.683-1.682a2.414 2.414 0 0 1 3.414 0z" />
    </IconBase>
  );
}

export function SidebarIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect x={3} y={3} width={18} height={18} rx={2} />
      <path d="M9 3v18" />
    </IconBase>
  );
}

export function FileIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
    </IconBase>
  );
}

export function FolderIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
    </IconBase>
  );
}

export function HideSidebarIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect x={3} y={3} width={18} height={18} rx={2} />
      <path d="M9 3v18" />
      <path d="m16 15-3-3 3-3" />
    </IconBase>
  );
}

export function OpenFileIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2" />
    </IconBase>
  );
}

export function CopyPathIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect x={8} y={8} width={14} height={14} rx={2} ry={2} />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </IconBase>
  );
}

export function ChevronDownSmallIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props} strokeWidth={2.25}>
      <path d="m6 9 6 6 6-6" />
    </IconBase>
  );
}

export function ChevronUpSmallIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props} strokeWidth={2.25}>
      <path d="m18 15-6-6-6 6" />
    </IconBase>
  );
}

export function NewFileIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
      <path d="M9 15h6" />
      <path d="M12 18v-6" />
    </IconBase>
  );
}

export function NewFolderIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 10v6" />
      <path d="M9 13h6" />
      <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
    </IconBase>
  );
}

export function CollapseAllIcon(props: IconProps) {
  return (
    // VS Code Codicon: "collapse-all"
    <IconBase viewBox="0 0 16 16" strokeWidth={0} {...props} stroke="none">
      <path d="M9 9H4v1h5V9z" fill="currentColor" />
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M5 3l1-1h7l1 1v7l-1 1h-2v2l-1 1H3l-1-1V6l1-1h2V3zm1 2h4l1 1v4h2V3H6v2zm4 1H3v7h7V6z"
        fill="currentColor"
      />
    </IconBase>
  );
}


export function DeleteIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M3 6h18" />
      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
      <line x1={10} x2={10} y1={11} y2={17} />
      <line x1={14} x2={14} y1={11} y2={17} />
    </IconBase>
  );
}

export function LogsIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M13 12h8" />
      <path d="M13 18h8" />
      <path d="M13 6h8" />
      <path d="M3 12h1" />
      <path d="M3 18h1" />
      <path d="M3 6h1" />
      <path d="M8 12h1" />
      <path d="M8 18h1" />
      <path d="M8 6h1" />
    </IconBase>
  );
}

export function OutputIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 17V3" />
      <path d="m6 11 6 6 6-6" />
      <path d="M19 21H5" />
    </IconBase>
  );
}

export function ConsoleIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <polyline points="4 17 10 11 4 5" />
      <line x1={12} x2={20} y1={19} y2={19} />
    </IconBase>
  );
}

export function WindowMaximizeIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M8 3H5a2 2 0 0 0-2 2v3" />
      <path d="M21 8V5a2 2 0 0 0-2-2h-3" />
      <path d="M3 16v3a2 2 0 0 0 2 2h3" />
      <path d="M16 21h3a2 2 0 0 0 2-2v-3" />
    </IconBase>
  );
}

export function WindowRestoreIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect x={8} y={8} width={14} height={14} rx={2} ry={2} />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </IconBase>
  );
}

export function MinimizeIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props} strokeWidth={2.25}>
      <path d="M5 12h14" />
    </IconBase>
  );
}

export function SaveIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" />
      <path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7" />
      <path d="M7 3v4a1 1 0 0 0 1 1h7" />
    </IconBase>
  );
}

export function SaveAllIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M10 2v3a1 1 0 0 0 1 1h5" />
      <path d="M18 18v-6a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6" />
      <path d="M18 22H4a2 2 0 0 1-2-2V6" />
      <path d="M8 18a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9.172a2 2 0 0 1 1.414.586l2.828 2.828A2 2 0 0 1 22 6.828V16a2 2 0 0 1-2.01 2z" />
    </IconBase>
  );
}

export function CloseOthersIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <line x1={12} x2={18} y1={12} y2={18} />
      <line x1={12} x2={18} y1={18} y2={12} />
      <rect x={8} y={8} width={14} height={14} rx={2} ry={2} />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </IconBase>
  );
}

export function CloseRightIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M3 5v14" />
      <path d="M21 12H7" />
      <path d="m15 18 6-6-6-6" />
    </IconBase>
  );
}

export function CloseAllIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect x={3} y={3} width={18} height={18} rx={2} ry={2} />
      <path d="m15 9-6 6" />
      <path d="m9 9 6 6" />
    </IconBase>
  );
}

export function DockWindowIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 3v18" />
      <path d="M3 12h18" />
      <rect x={3} y={3} width={18} height={18} rx={2} />
    </IconBase>
  );
}

export function DockRestoreIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect x={3} y={3} width={18} height={18} rx={2} />
    </IconBase>
  );
}

export function DockCloseIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect x={3} y={3} width={18} height={18} rx={2} ry={2} />
      <path d="m15 9-6 6" />
      <path d="m9 9 6 6" />
    </IconBase>
  );
}

export function ActionsIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={12} cy={12} r={1} />
      <circle cx={19} cy={12} r={1} />
      <circle cx={5} cy={12} r={1} />
    </IconBase>
  );
}

export function SpinnerIcon(props: IconProps) {
  return (
    <IconBase {...props} viewBox="0 0 24 24" strokeWidth={2.4}>
      <circle cx={12} cy={12} r={9} opacity={0.2} />
      {/* Lucide loader-circle arc */}
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </IconBase>
  );
}

export function TabSavingSpinner(props: IconProps) {
  return (
    <IconBase {...ICON_16} {...props} strokeWidth={1.6}>
      <circle cx={8} cy={8} r={6} opacity={0.3} />
      <path d="M14 8a6 6 0 0 0-6-6" />
    </IconBase>
  );
}

export function RunIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props} stroke="none">
      <polygon points="6 3 20 12 6 21 6 3" fill="currentColor" />
    </IconBase>
  );
}

export function PinGlyph({
  filled,
  className,
}: {
  readonly filled: boolean;
  readonly className?: string;
}) {
  // Lucide "pin" glyph, adapted for small (16px) usage by using the 24px
  // geometry with a strokeWidth scaled to visually match the rest of the 16px set.
  const PIN_16 = { viewBox: "0 0 24 24", strokeWidth: 2.1 };

  return (
    <IconBase {...PIN_16} className={className} stroke={filled ? "none" : undefined}>
      {filled ? (
        <g>
          <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z" fill="currentColor" />
          <rect x="11.1" y="17" width="1.8" height="5" rx="0.9" fill="currentColor" />
        </g>
      ) : (
        <g>
          <path d="M12 17v5" />
          <path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z" />
        </g>
      )}
    </IconBase>
  );
}

export function ChevronRightTinyIcon(props: IconProps) {
  return (
    <IconBase {...ICON_10} {...props}>
      <path d="M3 1l4 4-4 4" />
    </IconBase>
  );
}

// -----------------------------
// Pro pack additions (Lucide)
// -----------------------------

export function PlusIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M5 12h14" />
      <path d="M12 5v14" />
    </IconBase>
  );
}

export function MinusIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M5 12h14" />
    </IconBase>
  );
}

export function PlusCircleIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={12} cy={12} r={10} />
      <path d="M8 12h8" />
      <path d="M12 8v8" />
    </IconBase>
  );
}

export function MinusCircleIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={12} cy={12} r={10} />
      <path d="M8 12h8" />
    </IconBase>
  );
}

export function PlusSquareIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect width={18} height={18} x={3} y={3} rx={2} />
      <path d="M8 12h8" />
      <path d="M12 8v8" />
    </IconBase>
  );
}

export function MinusSquareIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect width={18} height={18} x={3} y={3} rx={2} />
      <path d="M8 12h8" />
    </IconBase>
  );
}

export function ArrowUpIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m5 12 7-7 7 7" />
      <path d="M12 19V5" />
    </IconBase>
  );
}

export function ArrowDownIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 5v14" />
      <path d="m19 12-7 7-7-7" />
    </IconBase>
  );
}

export function ArrowLeftIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m12 19-7-7 7-7" />
      <path d="M19 12H5" />
    </IconBase>
  );
}

export function ArrowRightIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </IconBase>
  );
}

export function ArrowUpRightIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M7 7h10v10" />
      <path d="M7 17 17 7" />
    </IconBase>
  );
}

export function ArrowDownRightIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m7 7 10 10" />
      <path d="M17 7v10H7" />
    </IconBase>
  );
}

export function ArrowDownLeftIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M17 7 7 17" />
      <path d="M17 17H7V7" />
    </IconBase>
  );
}

export function ArrowUpLeftIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M7 17V7h10" />
      <path d="M17 17 7 7" />
    </IconBase>
  );
}

export function ChevronUpIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m18 15-6-6-6 6" />
    </IconBase>
  );
}

export function ChevronUpDownIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m7 15 5 5 5-5" />
      <path d="m7 9 5-5 5 5" />
    </IconBase>
  );
}

export function ChevronsLeftIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m11 17-5-5 5-5" />
      <path d="m18 17-5-5 5-5" />
    </IconBase>
  );
}

export function ChevronsRightIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m6 17 5-5-5-5" />
      <path d="m13 17 5-5-5-5" />
    </IconBase>
  );
}

export function ChevronsUpIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m17 11-5-5-5 5" />
      <path d="m17 18-5-5-5 5" />
    </IconBase>
  );
}

export function ChevronsDownIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m7 6 5 5 5-5" />
      <path d="m7 13 5 5 5-5" />
    </IconBase>
  );
}

export function ExpandIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m15 15 6 6" />
      <path d="m15 9 6-6" />
      <path d="M21 16v5h-5" />
      <path d="M21 8V3h-5" />
      <path d="M3 16v5h5" />
      <path d="m3 21 6-6" />
      <path d="M3 8V3h5" />
      <path d="M9 9 3 3" />
    </IconBase>
  );
}

export function CollapseIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m15 15 6 6m-6-6v4.8m0-4.8h4.8" />
      <path d="M9 19.8V15m0 0H4.2M9 15l-6 6" />
      <path d="M15 4.2V9m0 0h4.8M15 9l6-6" />
      <path d="M9 4.2V9m0 0H4.2M9 9 3 3" />
    </IconBase>
  );
}

export function EditIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z" />
      <path d="m15 5 4 4" />
    </IconBase>
  );
}

export function CopyIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect width={14} height={14} x={8} y={8} rx={2} ry={2} />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </IconBase>
  );
}

export function DuplicateIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect width={14} height={14} x={8} y={8} rx={2} ry={2} />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </IconBase>
  );
}

export function CutIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={6} cy={6} r={3} />
      <path d="M8.12 8.12 12 12" />
      <path d="M20 4 8.12 15.88" />
      <circle cx={6} cy={18} r={3} />
      <path d="M14.8 14.8 20 20" />
    </IconBase>
  );
}

export function PasteIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M11 14h10" />
      <path d="M16 4h2a2 2 0 0 1 2 2v1.344" />
      <path d="m17 18 4-4-4-4" />
      <path d="M8 4H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 1.793-1.113" />
      <rect x={8} y={2} width={8} height={4} rx={1} />
    </IconBase>
  );
}

export function UndoIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M9 14 4 9l5-5" />
      <path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5a5.5 5.5 0 0 1-5.5 5.5H11" />
    </IconBase>
  );
}

export function RedoIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m15 14 5-5-5-5" />
      <path d="M20 9H9.5A5.5 5.5 0 0 0 4 14.5A5.5 5.5 0 0 0 9.5 20H13" />
    </IconBase>
  );
}

export function FilterIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M10 20a1 1 0 0 0 .553.895l2 1A1 1 0 0 0 14 21v-7a2 2 0 0 1 .517-1.341L21.74 4.67A1 1 0 0 0 21 3H3a1 1 0 0 0-.742 1.67l7.225 7.989A2 2 0 0 1 10 14z" />
    </IconBase>
  );
}

export function SortAscIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m3 8 4-4 4 4" />
      <path d="M7 4v16" />
      <path d="M11 12h4" />
      <path d="M11 16h7" />
      <path d="M11 20h10" />
    </IconBase>
  );
}

export function SortDescIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m3 16 4 4 4-4" />
      <path d="M7 20V4" />
      <path d="M11 4h10" />
      <path d="M11 8h7" />
      <path d="M11 12h4" />
    </IconBase>
  );
}

export function EyeIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0" />
      <circle cx={12} cy={12} r={3} />
    </IconBase>
  );
}

export function EyeOffIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49" />
      <path d="M14.084 14.158a3 3 0 0 1-4.242-4.242" />
      <path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143" />
      <path d="m2 2 20 20" />
    </IconBase>
  );
}

export function LockIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect width={18} height={11} x={3} y={11} rx={2} ry={2} />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </IconBase>
  );
}

export function UnlockIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <rect width={18} height={11} x={3} y={11} rx={2} ry={2} />
      <path d="M7 11V7a5 5 0 0 1 9.9-1" />
    </IconBase>
  );
}

export function HelpIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={12} cy={12} r={10} />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <path d="M12 17h.01" />
    </IconBase>
  );
}

export function LinkOffIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M9 17H7A5 5 0 0 1 7 7" />
      <path d="M15 7h2a5 5 0 0 1 4 8" />
      <line x1={8} x2={12} y1={12} y2={12} />
      <line x1={2} x2={22} y1={2} y2={22} />
    </IconBase>
  );
}

export function ShareIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={18} cy={5} r={3} />
      <circle cx={6} cy={12} r={3} />
      <circle cx={18} cy={19} r={3} />
      <line x1={8.59} x2={15.42} y1={13.51} y2={17.49} />
      <line x1={15.41} x2={8.59} y1={6.51} y2={10.49} />
    </IconBase>
  );
}

export function BellIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M10.268 21a2 2 0 0 0 3.464 0" />
      <path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326" />
    </IconBase>
  );
}

export function BellOffIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M10.268 21a2 2 0 0 0 3.464 0" />
      <path d="M17 17H4a1 1 0 0 1-.74-1.673C4.59 13.956 6 12.499 6 8a6 6 0 0 1 .258-1.742" />
      <path d="m2 2 20 20" />
      <path d="M8.668 3.01A6 6 0 0 1 18 8c0 2.687.77 4.653 1.707 6.05" />
    </IconBase>
  );
}

export function StarIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z" />
    </IconBase>
  );
}

export function StarOffIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M8.34 8.34 2 9.27l5 4.87L5.82 21 12 17.77 18.18 21l-.59-3.43" />
      <path d="M18.42 12.76 22 9.27l-6.91-1L12 2l-1.44 2.91" />
      <line x1={2} x2={22} y1={2} y2={22} />
    </IconBase>
  );
}

export function HeartIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M2 9.5a5.5 5.5 0 0 1 9.591-3.676.56.56 0 0 0 .818 0A5.49 5.49 0 0 1 22 9.5c0 2.29-1.5 4-3 5.5l-5.492 5.313a2 2 0 0 1-3 .019L5 15c-1.5-1.5-3-3.2-3-5.5" />
    </IconBase>
  );
}

export function HeartOffIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M10.5 4.893a5.5 5.5 0 0 1 1.091.931.56.56 0 0 0 .818 0A5.49 5.49 0 0 1 22 9.5c0 1.872-1.002 3.356-2.187 4.655" />
      <path d="m16.967 16.967-3.459 3.346a2 2 0 0 1-3 .019L5 15c-1.5-1.5-3-3.2-3-5.5a5.5 5.5 0 0 1 2.747-4.761" />
      <path d="m2 2 20 20" />
    </IconBase>
  );
}

export function BookmarkIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z" />
    </IconBase>
  );
}

export function TagIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z" />
      <circle cx={7.5} cy={7.5} r=".5" fill="currentColor" />
    </IconBase>
  );
}

export function LayersIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z" />
      <path d="M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12" />
      <path d="M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17" />
    </IconBase>
  );
}

export function CodeIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m16 18 6-6-6-6" />
      <path d="m8 6-6 6 6 6" />
    </IconBase>
  );
}

export function BracesIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M8 3H7a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5c0 1.1.9 2 2 2h1" />
      <path d="M16 21h1a2 2 0 0 0 2-2v-5c0-1.1.9-2 2-2a2 2 0 0 1-2-2V5a2 2 0 0 0-2-2h-1" />
    </IconBase>
  );
}

export function BracketsIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M16 3h3a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1h-3" />
      <path d="M8 21H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h3" />
    </IconBase>
  );
}

export function TerminalIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 19h8" />
      <path d="m4 17 6-6-6-6" />
    </IconBase>
  );
}

export function BugIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 20v-9" />
      <path d="M14 7a4 4 0 0 1 4 4v3a6 6 0 0 1-12 0v-3a4 4 0 0 1 4-4z" />
      <path d="M14.12 3.88 16 2" />
      <path d="M21 21a4 4 0 0 0-3.81-4" />
      <path d="M21 5a4 4 0 0 1-3.55 3.97" />
      <path d="M22 13h-4" />
      <path d="M3 21a4 4 0 0 1 3.81-4" />
      <path d="M3 5a4 4 0 0 0 3.55 3.97" />
      <path d="M6 13H2" />
      <path d="m8 2 1.88 1.88" />
      <path d="M9 7.13V6a3 3 0 1 1 6 0v1.13" />
    </IconBase>
  );
}

export function HistoryIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" />
      <path d="M12 7v5l4 2" />
    </IconBase>
  );
}

export function GitBranchIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <line x1={6} x2={6} y1={3} y2={15} />
      <circle cx={18} cy={6} r={3} />
      <circle cx={6} cy={18} r={3} />
      <path d="M18 9a9 9 0 0 1-9 9" />
    </IconBase>
  );
}

export function GitCommitIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={12} cy={12} r={3} />
      <line x1={3} x2={9} y1={12} y2={12} />
      <line x1={15} x2={21} y1={12} y2={12} />
    </IconBase>
  );
}

export function GitPullRequestIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={18} cy={18} r={3} />
      <circle cx={6} cy={6} r={3} />
      <path d="M13 6h3a2 2 0 0 1 2 2v7" />
      <line x1={6} x2={6} y1={9} y2={21} />
    </IconBase>
  );
}

export function GitMergeIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={18} cy={18} r={3} />
      <circle cx={6} cy={6} r={3} />
      <path d="M6 21V9a9 9 0 0 0 9 9" />
    </IconBase>
  );
}

export function GitCompareIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <circle cx={18} cy={18} r={3} />
      <circle cx={6} cy={6} r={3} />
      <path d="M13 6h3a2 2 0 0 1 2 2v7" />
      <path d="M11 18H8a2 2 0 0 1-2-2V9" />
    </IconBase>
  );
}

export function FolderOpenIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2" />
    </IconBase>
  );
}

export function FolderPlusIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 10v6" />
      <path d="M9 13h6" />
      <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
    </IconBase>
  );
}

export function FolderMinusIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M9 13h6" />
      <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
    </IconBase>
  );
}

export function FolderSearchIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M10.7 20H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H20a2 2 0 0 1 2 2v4.1" />
      <path d="m21 21-1.9-1.9" />
      <circle cx={17} cy={17} r={3} />
    </IconBase>
  );
}

export function FilePlusIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" />
      <path d="M14 2v5a1 1 0 0 0 1 1h5" />
      <path d="M9 15h6" />
      <path d="M12 18v-6" />
    </IconBase>
  );
}

export function FileMinusIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" />
      <path d="M14 2v5a1 1 0 0 0 1 1h5" />
      <path d="M9 15h6" />
    </IconBase>
  );
}

export function FileSearchIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" />
      <path d="M14 2v5a1 1 0 0 0 1 1h5" />
      <circle cx={11.5} cy={14.5} r={2.5} />
      <path d="M13.3 16.3 15 18" />
    </IconBase>
  );
}

export function FileCodeIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" />
      <path d="M14 2v5a1 1 0 0 0 1 1h5" />
      <path d="M10 12.5 8 15l2 2.5" />
      <path d="m14 12.5 2 2.5-2 2.5" />
    </IconBase>
  );
}

export function CloudIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z" />
    </IconBase>
  );
}

export function CloudUploadIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 13v8" />
      <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
      <path d="m8 17 4-4 4 4" />
    </IconBase>
  );
}

export function CloudDownloadIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 13v8l-4-4" />
      <path d="m12 21 4-4" />
      <path d="M4.393 15.269A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.436 8.284" />
    </IconBase>
  );
}

export function DatabaseIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <ellipse cx={12} cy={5} rx={9} ry={3} />
      <path d="M3 5V19A9 3 0 0 0 21 19V5" />
      <path d="M3 12A9 3 0 0 0 21 12" />
    </IconBase>
  );
}

export function TableIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M12 3v18" />
      <rect width={18} height={18} x={3} y={3} rx={2} />
      <path d="M3 9h18" />
      <path d="M3 15h18" />
    </IconBase>
  );
}

export function ChartLineIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M3 3v16a2 2 0 0 0 2 2h16" />
      <path d="m19 9-5 5-4-4-3 3" />
    </IconBase>
  );
}

export function ChartBarIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M3 3v16a2 2 0 0 0 2 2h16" />
      <path d="M18 17V9" />
      <path d="M13 17V5" />
      <path d="M8 17v-3" />
    </IconBase>
  );
}

export function KeyIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4" />
      <path d="m21 2-9.6 9.6" />
      <circle cx={7.5} cy={15.5} r={5.5} />
    </IconBase>
  );
}

export function ShieldIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
    </IconBase>
  );
}

export function ShieldCheckIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" />
      <path d="m9 12 2 2 4-4" />
    </IconBase>
  );
}

export function SparklesIcon(props: IconProps) {
  return (
    <IconBase {...ICON_24} {...props}>
      <path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z" />
      <path d="M20 2v4" />
      <path d="M22 4h-4" />
      <circle cx={4} cy={20} r={2} />
    </IconBase>
  );
}
