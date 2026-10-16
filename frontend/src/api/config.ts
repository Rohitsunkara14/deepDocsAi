// Production never silently directs users to their own localhost backend.
export function apiBaseUrl(
  configured: string | undefined,
  development: boolean,
): string {
  return configured || (development ? "http://localhost:8000" : "");
}
