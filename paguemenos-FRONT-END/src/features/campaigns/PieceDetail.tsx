import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import type { Decision, Piece, ReviewRequest, ValidationRun } from "@/contracts/api"
import { PieceVisual } from "@/features/campaigns/PieceVisual"
import { formatPrice } from "@/features/catalog/format-price"

const labels = { draft: "Rascunho", validated: "Validada", approved: "Aprovada", rejected: "Rejeitada" }
const severityLabels = { critical: "Crítica", warning: "Aviso", info: "Informação" }
const reviewSchema = z.object({
  reviewer_id: z.string().trim().min(1, "Informe o revisor.").max(100, "Use até 100 caracteres."),
  comment: z.string().trim().max(2000, "Use até 2000 caracteres."),
})
type ReviewValues = z.infer<typeof reviewSchema>
const fieldClass = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 focus-visible:outline-blue-700"

function ValidationResults({ run }: { run: ValidationRun }) {
  return <div className="mt-3 space-y-3">
    <p className="font-semibold text-blue-950">{run.success ? "Sem violações críticas" : "Validação com bloqueios críticos"}</p>
    <p className="text-xs text-slate-500">{new Date(run.created_at).toLocaleString("pt-BR")}</p>
    <ul className="space-y-2">
      {run.results.map((result, index) => <li key={`${result.rule_code}-${index}`} className={`rounded-lg border p-3 text-sm ${result.passed ? "border-slate-200 bg-slate-50" : result.severity === "critical" ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"}`}>
        <p className="font-semibold">{result.passed ? "Aprovada" : "Violação"} · {severityLabels[result.severity]}</p>
        <p className="mt-1 break-words">{result.message}</p>
        <p className="mt-1 break-words text-xs text-slate-600">{result.rule_code} · {result.field}</p>
      </li>)}
    </ul>
  </div>
}

export function PieceDetail({ piece, campaignId, sourcePieces, busy, onBusyChange, onReview }: { piece: Piece; campaignId: string; sourcePieces: Piece[]; busy: boolean; onBusyChange: (id: string, active: boolean) => void; onReview: (id: string, review: ReviewRequest) => Promise<boolean> }) {
  const [decision, setDecision] = useState<Decision | null>(null)
  const { register, handleSubmit, getValues, formState: { errors } } = useForm<ReviewValues>({ resolver: zodResolver(reviewSchema), defaultValues: { reviewer_id: "", comment: "" } })
  const latest = piece.validations.at(-1)
  const canApprove = piece.state === "validated" && latest?.success === true
  async function confirm() {
    if (!decision || busy || (decision === "approved" && !canApprove)) return
    const values = getValues()
    setDecision(null)
    await onReview(piece.id, { decision, reviewer_id: values.reviewer_id.trim(), comment: values.comment.trim() || null })
  }
  return <article className="space-y-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7" aria-label={`Peça ${piece.channel}`}>
    <header className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="text-xl font-bold text-blue-950">Peça · {piece.channel}</h2>
      <span className="rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-950">{labels[piece.state]}</span>
    </header>
    <dl className="grid gap-4 text-sm sm:grid-cols-2">
      {[["Título", piece.title], ["Subtítulo", piece.subtitle], ["CTA", piece.cta], ["Disclaimer", piece.disclaimer], ["Produto", `${piece.product_name} (${piece.product_id})`], ["Preço", formatPrice(piece.price)], ["Oferta autorizada", piece.authorized_offer]].map(([label, value]) => <div key={label} className="min-w-0"><dt className="font-semibold text-blue-950">{label}</dt><dd className="mt-1 whitespace-pre-wrap break-words text-slate-700">{value}</dd></div>)}
    </dl>
    <PieceVisual piece={piece} campaignId={campaignId} sourcePieces={sourcePieces} disabled={busy} onBusyChange={onBusyChange} />
    <section className="border-t border-slate-200 pt-5" aria-label="Brand Guardian">
      <h3 className="text-lg font-bold text-blue-950">Brand Guardian</h3>
      {latest ? <ValidationResults run={latest} /> : <p className="mt-2 text-sm text-slate-600">Esta peça ainda não foi validada.</p>}
      {piece.validations.length > 1 && <details className="mt-4"><summary className="cursor-pointer font-semibold text-blue-900">Validações anteriores ({piece.validations.length - 1})</summary>{piece.validations.slice(0, -1).map((run) => <ValidationResults key={run.id} run={run} />)}</details>}
    </section>
    <section className="border-t border-slate-200 pt-5">
      <h3 className="text-lg font-bold text-blue-950">Revisão humana</h3>
      <p className="mt-1 text-sm text-slate-600">Informe sua identificação de revisor para registrar a decisão.</p>
      {!canApprove && <p className="mt-2 text-sm text-slate-600">A aprovação exige estado Validada e última validação bem-sucedida. Peças rejeitadas precisam ser revalidadas.</p>}
      <form className="mt-4 space-y-4" onSubmit={handleSubmit(() => setDecision("approved"))} noValidate>
        <fieldset disabled={busy || decision !== null} className="space-y-4 disabled:opacity-60">
          <div><label htmlFor={`reviewer-${piece.id}`} className="text-sm font-semibold text-blue-950">Identificação do revisor</label><input id={`reviewer-${piece.id}`} maxLength={100} className={fieldClass} aria-invalid={Boolean(errors.reviewer_id)} {...register("reviewer_id")} />{errors.reviewer_id && <p role="alert" className="text-sm text-red-700">{errors.reviewer_id.message}</p>}</div>
          <div><label htmlFor={`comment-${piece.id}`} className="text-sm font-semibold text-blue-950">Comentário da revisão (opcional)</label><textarea id={`comment-${piece.id}`} rows={3} maxLength={2000} className={fieldClass} {...register("comment")} />{errors.comment && <p role="alert" className="text-sm text-red-700">{errors.comment.message}</p>}</div>
          <div className="flex flex-wrap gap-3"><Button type="submit" disabled={!canApprove}>Aprovar</Button><Button type="button" variant="outline" onClick={() => void handleSubmit(() => setDecision("rejected"))()}>Rejeitar</Button></div>
        </fieldset>
      </form>
      {decision && <div role="group" aria-label="Confirmar revisão" className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm">
        <p>Confirmar {decision === "approved" ? "aprovação" : "rejeição"} desta peça? A decisão será registrada no histórico.</p>
        <div className="mt-3 flex flex-wrap gap-3"><Button type="button" disabled={busy || (decision === "approved" && !canApprove)} onClick={() => void confirm()}>Confirmar {decision === "approved" ? "aprovação" : "rejeição"}</Button><Button type="button" variant="outline" disabled={busy} onClick={() => setDecision(null)}>Cancelar</Button></div>
      </div>}
      <details className="mt-5" open={piece.reviews.length > 0}>
        <summary className="cursor-pointer text-sm font-semibold text-blue-900">Histórico de revisões ({piece.reviews.length})</summary>
        <ul className="mt-3 space-y-3 text-sm">{piece.reviews.map((review) => <li key={review.id} className="rounded-lg bg-slate-50 p-3"><p className="font-semibold">{labels[review.decision]} · {review.reviewer_id}</p><p className="text-xs text-slate-500">{new Date(review.created_at).toLocaleString("pt-BR")}</p>{review.comment && <p className="mt-2 whitespace-pre-wrap break-words">{review.comment}</p>}</li>)}</ul>
      </details>
    </section>
  </article>
}
