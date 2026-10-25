import type { ReactNode } from "react"
import { normalizeHttpError } from "@/api/errors"

export function LoadingState({ label = "Carregando…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-blue-100 bg-white p-5 text-sm text-slate-600" role="status">
      <span className="size-4 animate-spin rounded-full border-2 border-blue-200 border-t-blue-700" aria-hidden="true" />
      {label}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const normalized = normalizeHttpError(error)
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-950" role="alert">
      <p className="font-semibold">Falha na solicitação</p>
      <p className="mt-1">{normalized.message}</p>
      {normalized.code && <p className="mt-2 text-xs">Código: {normalized.code}</p>}
      {onRetry && (
        <button type="button" onClick={onRetry} className="mt-4 rounded-lg border border-red-300 px-3 py-2 font-medium hover:bg-red-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-700">
          Tentar novamente
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center" role="status">
      <p className="font-semibold text-slate-800">{title}</p>
      {children && <div className="mt-1 text-sm text-slate-600">{children}</div>}
    </div>
  )
}
