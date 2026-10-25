const defaultApiBaseUrl = "http://127.0.0.1:8000"

function resolveApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim() || defaultApiBaseUrl
  if (configured.startsWith("/") && !configured.startsWith("//")) {
    return configured.replace(/\/+$/, "")
  }
  const url = new URL(configured)
  if (!(["http:", "https:"].includes(url.protocol))) {
    throw new Error("VITE_API_BASE_URL deve usar http ou https.")
  }
  return configured.replace(/\/+$/, "")
}

export const env = { apiBaseUrl: resolveApiBaseUrl() } as const
