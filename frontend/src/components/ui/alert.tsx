interface AlertProps {
  tone?: "error" | "success" | "info";
  children: React.ReactNode;
  className?: string;
}

const TONES: Record<NonNullable<AlertProps["tone"]>, string> = {
  error:
    "bg-red-50 border-red-200 text-red-700 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300",
  success:
    "bg-emerald-50 border-emerald-200 text-emerald-700 dark:bg-emerald-900/20 dark:border-emerald-800 dark:text-emerald-300",
  info: "bg-indigo-50 border-indigo-200 text-indigo-800 dark:bg-indigo-900/20 dark:border-indigo-800 dark:text-indigo-300",
};

/**
 * Standard inline notice (form errors, success states). Replaces ad-hoc alert divs.
 */
export function Alert({ tone = "error", children, className = "" }: AlertProps) {
  return (
    <div
      className={`rounded-xl border p-3 text-sm ${TONES[tone]} ${className}`}
      role={tone === "error" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}
