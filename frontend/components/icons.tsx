import type { SVGProps } from "react";

export function Icon({
  name,
  ...props
}: SVGProps<SVGSVGElement> & {
  name:
    | "cases"
    | "policy"
    | "audit"
    | "arrow"
    | "upload"
    | "close"
    | "logout"
    | "source"
    | "plus"
    | "check";
}) {
  const paths = {
    cases: (
      <>
        <path d="M4 7.5h16v11H4z" />
        <path d="M8 7.5v-2h8v2" />
      </>
    ),
    policy: (
      <>
        <path d="M6 3.5h9l3 3v14H6z" />
        <path d="M15 3.5v4h4M9 12h6M9 16h6" />
      </>
    ),
    audit: (
      <>
        <circle cx="12" cy="12" r="8.5" />
        <path d="M12 7.5V12l3 2" />
      </>
    ),
    arrow: <path d="m9 5 7 7-7 7" />,
    upload: (
      <>
        <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" />
        <path d="M5 15v4h14v-4" />
      </>
    ),
    close: <path d="m6 6 12 12M18 6 6 18" />,
    logout: <path d="M10 4H5v16h5M14 8l4 4-4 4m4-4H9" />,
    source: (
      <>
        <path d="M7 4h10v16H7z" />
        <path d="M10 9h4M10 13h4" />
      </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    check: <path d="m5 12 4 4 10-10" />,
  };
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
