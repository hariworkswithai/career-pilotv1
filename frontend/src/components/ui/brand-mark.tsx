interface BrandMarkProps {
  className?: string;
  /** "tile" renders the mark on a navy rounded tile; "mark" renders the bare swirl. */
  variant?: "tile" | "mark";
}

/**
 * CareerPilot brand mark: a navigation swirl in brand navy.
 * Single source of truth for the logo across sidebar, header, landing and auth.
 */
export function BrandMark({ className = "h-8 w-8", variant = "tile" }: BrandMarkProps) {
  if (variant === "mark") {
    return (
      <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M20.6 12a8.6 8.6 0 1 1-2.9-6.4"
          stroke="currentColor"
          strokeWidth={2.4}
          strokeLinecap="round"
        />
        <path
          d="M20.9 2.8v4.1h-4.1"
          stroke="currentColor"
          strokeWidth={2.4}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="12" cy="12" r="2.1" fill="currentColor" />
      </svg>
    );
  }
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-xl bg-indigo-700 ${className}`}
      aria-hidden="true"
    >
      <svg className="h-[62%] w-[62%]" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M20.6 12a8.6 8.6 0 1 1-2.9-6.4"
          stroke="#ffffff"
          strokeWidth={2.4}
          strokeLinecap="round"
        />
        <path
          d="M20.9 2.8v4.1h-4.1"
          stroke="#ffffff"
          strokeWidth={2.4}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="12" cy="12" r="2.1" fill="#ffffff" />
      </svg>
    </span>
  );
}
