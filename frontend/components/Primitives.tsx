"use client";

import type { ButtonHTMLAttributes, ReactNode, Ref, SVGProps } from "react";

export function cx(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(" ");
}

/* -------------------------------------------------------------------------- */
/* Layout                                                                      */
/* -------------------------------------------------------------------------- */

export function Panel({
  children,
  className,
  ...rest
}: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLElement>) {
  return (
    <section className={cx("panel", className)} {...rest}>
      {children}
    </section>
  );
}

export function SectionHeading({
  title,
  hint,
  action,
  id,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
  id?: string;
}) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div>
        <h2 id={id} className="text-base font-semibold tracking-tight text-ink-900">
          {title}
        </h2>
        {hint ? <p className="mt-1 text-sm text-ink-500">{hint}</p> : null}
      </div>
      {action}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Controls                                                                    */
/* -------------------------------------------------------------------------- */

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  /** React 19 passes refs to function components as a normal prop. */
  ref?: Ref<HTMLButtonElement>;
};

const VARIANTS: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary:
    "bg-accent-600 text-white hover:bg-accent-700 disabled:bg-ink-200 disabled:text-ink-400",
  secondary:
    "bg-ink-100 text-ink-800 hover:bg-ink-200 disabled:bg-ink-100 disabled:text-ink-400",
  ghost: "text-ink-600 hover:bg-ink-100 hover:text-ink-900 disabled:text-ink-300",
  danger: "bg-red-600 text-white hover:bg-red-700 disabled:bg-ink-200 disabled:text-ink-400",
};

const SIZES: Record<NonNullable<ButtonProps["size"]>, string> = {
  sm: "px-2.5 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-3 text-sm",
};

export function Button({
  variant = "secondary",
  size = "md",
  className,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors",
        "disabled:cursor-not-allowed",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    />
  );
}

/* -------------------------------------------------------------------------- */
/* Feedback                                                                    */
/* -------------------------------------------------------------------------- */

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cx("h-4 w-4 animate-spin", className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function EmptyState({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-xl bg-ink-50 px-6 py-10 text-center">
      {icon ? <div className="mb-3 text-ink-300">{icon}</div> : null}
      <p className="text-sm font-medium text-ink-800">{title}</p>
      <p className="mt-1 max-w-sm text-sm text-ink-500">{description}</p>
    </div>
  );
}

export function Alert({
  tone = "error",
  title,
  children,
}: {
  tone?: "error" | "info" | "success";
  title?: string;
  children: ReactNode;
}) {
  const tones = {
    error: "bg-red-50 text-red-900",
    info: "bg-accent-50 text-accent-900",
    success: "bg-emerald-50 text-emerald-900",
  } as const;
  return (
    <div className={cx("flex gap-3 rounded-xl p-4 text-sm", tones[tone])} role="alert">
      <span aria-hidden="true" className="mt-0.5 shrink-0">
        {tone === "error" ? <IconAlert /> : tone === "success" ? <IconCheck /> : <IconInfo />}
      </span>
      <div>
        {title ? <p className="font-medium">{title}</p> : null}
        <div className={title ? "mt-0.5" : undefined}>{children}</div>
      </div>
    </div>
  );
}

/**
 * Status chip. Shape and text carry the meaning, colour only reinforces it,
 * so the status is still readable without colour vision.
 */
export function StatusChip({
  label,
  tone,
  icon,
}: {
  label: string;
  tone: "neutral" | "busy" | "success" | "error";
  icon?: ReactNode;
}) {
  const tones = {
    neutral: "bg-ink-100 text-ink-600",
    busy: "bg-accent-50 text-accent-800",
    success: "bg-emerald-50 text-emerald-800",
    error: "bg-red-50 text-red-800",
  } as const;
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
        tones[tone],
      )}
    >
      {icon}
      {label}
    </span>
  );
}

export function ProgressBar({
  value,
  label,
  indeterminate = false,
}: {
  value: number;
  label: string;
  indeterminate?: boolean;
}) {
  return (
    <div
      className="h-1.5 w-full overflow-hidden rounded-full bg-ink-100"
      role="progressbar"
      aria-label={label}
      aria-valuenow={indeterminate ? undefined : Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cx(
          "h-full rounded-full bg-accent-600 transition-[width] duration-300",
          indeterminate && "animate-pulse",
        )}
        style={{ width: `${Math.max(2, Math.min(100, value))}%` }}
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Icons — inline so the app ships without an icon dependency                   */
/* -------------------------------------------------------------------------- */

type IconProps = SVGProps<SVGSVGElement>;

function base(props: IconProps) {
  return {
    width: 16,
    height: 16,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
    ...props,
  };
}

export const IconUpload = (props: IconProps) => (
  <svg {...base(props)}>
    <path d="M12 16V4m0 0L7 9m5-5 5 5" />
    <path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
  </svg>
);

export const IconFile = (props: IconProps) => (
  <svg {...base(props)}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
  </svg>
);

export const IconTrash = (props: IconProps) => (
  <svg {...base(props)}>
    <path d="M4 7h16M10 11v6M14 11v6" />
    <path d="M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
  </svg>
);

export const IconCheck = (props: IconProps) => (
  <svg {...base(props)}>
    <path d="M5 13l4 4L19 7" />
  </svg>
);

export const IconAlert = (props: IconProps) => (
  <svg {...base(props)}>
    <path d="M12 9v4M12 17h.01" />
    <path d="M10.3 3.9 2.4 17a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
  </svg>
);

export const IconInfo = (props: IconProps) => (
  <svg {...base(props)}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5M12 8h.01" />
  </svg>
);

export const IconSearch = (props: IconProps) => (
  <svg {...base(props)}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

export const IconChevronLeft = (props: IconProps) => (
  <svg {...base(props)}>
    <path d="m15 18-6-6 6-6" />
  </svg>
);

export const IconChevronRight = (props: IconProps) => (
  <svg {...base(props)}>
    <path d="m9 18 6-6-6-6" />
  </svg>
);

export const IconLayers = (props: IconProps) => (
  <svg {...base(props)}>
    <path d="m12 3 9 5-9 5-9-5 9-5z" />
    <path d="m3 13 9 5 9-5" />
  </svg>
);

export const IconDatabase = (props: IconProps) => (
  <svg {...base(props)}>
    <ellipse cx="12" cy="6" rx="8" ry="3" />
    <path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6" />
    <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
  </svg>
);

export const IconSpark = (props: IconProps) => (
  <svg {...base(props)}>
    <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8" />
  </svg>
);
