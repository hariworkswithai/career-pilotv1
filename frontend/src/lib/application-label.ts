export function externalUrlLabel(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, "").split(".")[0] ?? "Open";
  } catch {
    return "Open";
  }
}