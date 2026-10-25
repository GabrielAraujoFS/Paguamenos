import axios from "axios"
import type { ApiErrorResponse } from "@/contracts/api"

export interface HttpError {
  kind: "http" | "network" | "unknown"
  status?: number
  code?: string
  message: string
  details: Array<Record<string, unknown>>
}

function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  if (!value || typeof value !== "object" || !("error" in value)) return false
  const error = value.error
  return Boolean(
    error && typeof error === "object" &&
      "code" in error && typeof error.code === "string" &&
      "message" in error && typeof error.message === "string" &&
      "details" in error && Array.isArray(error.details),
  )
}

export function normalizeHttpError(error: unknown): HttpError {
  if (axios.isAxiosError(error)) {
    const body: unknown = error.response?.data
    if (isApiErrorResponse(body)) {
      return {
        kind: "http",
        status: error.response?.status,
        code: body.error.code,
        message: body.error.message,
        details: body.error.details,
      }
    }
    if (error.response) {
      return {
        kind: "http",
        status: error.response.status,
        message: `A solicitação falhou (HTTP ${error.response.status}).`,
        details: [],
      }
    }
    return { kind: "network", message: "Não foi possível conectar ao backend.", details: [] }
  }
  return { kind: "unknown", message: "Ocorreu um erro inesperado.", details: [] }
}
