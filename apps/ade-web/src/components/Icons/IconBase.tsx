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
