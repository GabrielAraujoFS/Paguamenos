import { useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { getRender, reviewPiece, startRender } from "@/api/services/campaigns"
import { queryKeys } from "@/api/query-keys"
import { normalizeHttpError } from "@/api/errors"
import type { Decision, Piece, RenderRequest, VisualProcessingState } from "@/contracts/api"
import { formatPrice } from "@/features/catalog/format-price"
import { PiecePreview } from "@/features/campaigns/PiecePreview"

const labels: Record<VisualProcessingState, string> = {
  pending: "Imagem ainda não gerada", processing: "Gerando fundo e compondo…",
  background_ready: "Fundo pronto; compondo peça…", composed: "Composição concluída",
  blocked: "Geração bloqueada", failed: "Falha na geração",
}
const buttonClass = "rounded-lg border border-blue-800 px-3 py-2 text-sm font-semibold text-blue-900 disabled:cursor-not-allowed disabled:opacity-50"

export function PieceDetail({ piece, campaignId, sourcePieces }: { piece: Piece; campaignId: string; sourcePieces: Piece[] }) {
  const queryClient = useQueryClient()
  const [error, setError] = useState<unknown>(null)
  const [reviewerId, setReviewerId] = useState("")
  const [comment, setComment] = useState("")
  const [sourcePieceId, setSourcePieceId] = useState("")
  const renderLock = useRef(false)
  const reviewLock = useRef(false)
  const lastRenderAt = useRef(0)
  const lastReviewAt = useRef(0)
  const previousState = useRef<VisualProcessingState | null>(null)
  const status = useQuery({
    queryKey: queryKeys.render(piece.id), queryFn: () => getRender(piece.id), retry: false,
    refetchInterval: (query) => {
      const state = query.state.data?.visual.state
      return state === "processing" || state === "background_ready" ? 1500 : false
    },
  })
  const renderMutation = useMutation({ mutationFn: (body: RenderRequest) => startRender(piece.id, body), retry: false })
  const reviewMutation = useMutation({ mutationFn: (body: { decision: Decision; reviewer_id: string; comment: string | null }) => reviewPiece(piece.id, body), retry: false })
  const visual = status.data?.visual
  const busy = visual?.state === "processing" || visual?.state === "background_ready"
  const latestValidation = piece.validations.at(-1)
  const validationFindings = latestValidation?.results ?? []
  const validationStatus = !latestValidation ? null : !latestValidation.success ? "Não conforme" :
    validationFindings.some((result) => !result.passed) ? "Revisão necessária" : "Conforme"
  const canApprove = piece.state === "validated" && latestValidation?.success === true && visual?.state === "composed"

  useEffect(() => {
    const state = visual?.state
    if (previousState.current && (previousState.current === "processing" || previousState.current === "background_ready") && state && state !== "processing" && state !== "background_ready") {
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaign(campaignId) })
    }
    if (state) previousState.current = state
  }, [visual?.state, campaignId, queryClient])

  async function renderPiece(body: Omit<RenderRequest, "request_id">) {
    if (renderLock.current || renderMutation.isPending || busy || Date.now() - lastRenderAt.current < 800) return
    renderLock.current = true
    lastRenderAt.current = Date.now()
    setError(null)
    try {
      const result = await renderMutation.mutateAsync({ ...body, request_id: crypto.randomUUID() })
      queryClient.setQueryData(queryKeys.render(piece.id), result)
      if (result.visual.state !== "processing" && result.visual.state !== "background_ready") {
        await queryClient.invalidateQueries({ queryKey: queryKeys.campaign(campaignId) })
      }
    } catch (cause) { setError(cause); lastRenderAt.current = 0 }
    finally { renderLock.current = false }
  }

  async function review(decision: Decision) {
    if (reviewLock.current || reviewMutation.isPending || Date.now() - lastReviewAt.current < 800 || !reviewerId.trim() || (decision === "approved" && !canApprove)) return
    reviewLock.current = true
    lastReviewAt.current = Date.now()
    setError(null)
    try {
      await reviewMutation.mutateAsync({ decision, reviewer_id: reviewerId.trim(), comment: comment.trim() || null })
      await queryClient.invalidateQueries({ queryKey: queryKeys.campaign(campaignId) })
      setComment("")
    } catch (cause) {
      setError(cause)
      lastReviewAt.current = 0
      if (normalizeHttpError(cause).status === 409) void queryClient.invalidateQueries({ queryKey: queryKeys.campaign(campaignId) })
    } finally { reviewLock.current = false }
  }

  return <article className="space-y-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-label={`Peça ${piece.channel}`}>
    <div><h2 className="text-xl font-bold text-blue-950">{piece.channel} · {piece.title}</h2><p className="text-sm text-slate-600">Estado editorial: {piece.state}</p></div>
    <div className="grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
      <p><strong>Produto:</strong> {piece.product_name}</p><p><strong>Preço autorizado:</strong> {formatPrice(piece.price)}</p>
      <p><strong>Oferta:</strong> {piece.authorized_offer}</p><p><strong>CTA:</strong> {piece.cta}</p>
      <p><strong>Subtítulo:</strong> {piece.subtitle}</p><p><strong>Nota:</strong> {piece.disclaimer}</p>
    </div>
    {status.isPending ? <p role="status">Consultando geração…</p> : status.isError ? <div role="alert">Falha ao consultar renderização: {normalizeHttpError(status.error).message} <button type="button" onClick={() => void status.refetch()} className="underline">Tentar novamente</button></div> : visual && <>
      <section className="space-y-2"><h3 className="font-semibold text-blue-950">Plano visual do Gemini</h3>
        {visual.plan ? <div className="grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
          <p><strong>Conceito:</strong> {visual.plan.concept || visual.plan.art_direction}</p>
          <p><strong>Estilo:</strong> {visual.plan.visual_style || "Não informado"}</p>
          <p><strong>Cenário:</strong> {visual.plan.scenario || "Não informado"}</p>
          <p><strong>Iluminação:</strong> {visual.plan.lighting || "Não informada"}</p>
          <p><strong>Template:</strong> {visual.template?.name || visual.plan.layout}</p>
          <p><strong>Paleta:</strong> {visual.plan.palette.join(", ") || "Não informada"}</p>
          <p className="sm:col-span-2"><strong>Direção de arte:</strong> {visual.plan.art_direction}</p>
          <p className="sm:col-span-2"><strong>Elementos:</strong> {visual.plan.decorative_elements.join(", ") || "Nenhum"}</p>
        </div> : <p className="text-sm text-amber-800">Esta campanha não possui plano visual. É necessário gerar uma nova campanha com o planejador habilitado.</p>}
      </section>
      <section className="space-y-3" aria-label="Renderização">
        <p role="status" className="font-semibold">{labels[visual.state]}</p>
        {visual.error_message && <p role="alert" className="text-sm text-red-800">{visual.error_message}{visual.error_code ? ` (${visual.error_code})` : ""}</p>}
        <div className="flex flex-wrap gap-2">
          <button type="button" className={buttonClass} disabled={!visual.plan || busy || renderMutation.isPending} onClick={() => void renderPiece({})}>Gerar imagem</button>
          <button type="button" className={buttonClass} disabled={!visual.plan || busy || renderMutation.isPending} onClick={() => void renderPiece({ regenerate_background: true })}>Gerar novo fundo</button>
          <button type="button" className={buttonClass} disabled={!visual.background || busy || renderMutation.isPending} onClick={() => void renderPiece({ force: true })}>Recompor com fundo existente</button>
        </div>
        {sourcePieces.length > 0 && <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm">Reutilizar fundo de outra peça
            <select value={sourcePieceId} onChange={(event) => setSourcePieceId(event.target.value)} className="mt-1 block rounded-lg border p-2">
              <option value="">Selecione uma peça do mesmo canal</option>
              {sourcePieces.map((source) => <option key={source.id} value={source.id}>{source.title} ({source.id})</option>)}
            </select>
          </label>
          <button type="button" className={buttonClass} disabled={!sourcePieceId || busy || renderMutation.isPending} onClick={() => void renderPiece({ source_piece_id: sourcePieceId })}>Usar fundo selecionado</button>
        </div>}
        {visual.state === "composed" && visual.final_image && <PiecePreview pieceId={piece.id} fileId={visual.final_image.file_id} title={piece.title} />}
        {visual.generation && <p className="text-xs text-slate-600">Plano: {visual.generation.provider} · {visual.generation.model}{visual.generation.total_tokens != null ? ` · ${visual.generation.total_tokens} tokens` : ""}</p>}
        {visual.image_generation && <p className="text-xs text-slate-600">Fundo: {visual.image_generation.model} · tentativa {visual.image_generation.attempts}{visual.image_generation.total_tokens != null ? ` · ${visual.image_generation.total_tokens} tokens` : ""}</p>}
      </section>
    </>}
    <section className="space-y-2"><h3 className="font-semibold text-blue-950">Validação BrandGuard</h3>
      {latestValidation ? <><p className="text-sm">Última validação: {validationStatus} · {new Date(latestValidation.created_at).toLocaleString("pt-BR")}</p>
        <ul className="space-y-1 text-sm">{validationFindings.map((result, index) => <li key={`${result.rule_code}-${index}`} className={result.passed ? "text-slate-700" : result.severity === "critical" ? "text-red-800" : "text-amber-800"}>{result.passed ? "✓" : result.severity === "critical" ? "✗" : "!"} {result.message}</li>)}</ul>
        <p className="text-xs text-slate-500">{piece.validations.length} validação(ões) no histórico.</p></> : <p className="text-sm text-slate-600">Aguardando validação.</p>}
    </section>
    <section className="space-y-3"><h3 className="font-semibold text-blue-950">Revisão humana</h3>
      <label className="block text-sm">Identificação do revisor (autodeclarada)<input value={reviewerId} onChange={(event) => setReviewerId(event.target.value)} maxLength={100} className="mt-1 block w-full rounded-lg border p-2" /></label>
      <label className="block text-sm">Comentário<input value={comment} onChange={(event) => setComment(event.target.value)} maxLength={2000} className="mt-1 block w-full rounded-lg border p-2" /></label>
      <div className="flex gap-2"><button type="button" className={buttonClass} disabled={!canApprove || !reviewerId.trim() || reviewMutation.isPending} onClick={() => void review("approved")}>Aprovar peça</button>
        <button type="button" className={buttonClass} disabled={!reviewerId.trim() || reviewMutation.isPending} onClick={() => void review("rejected")}>Rejeitar peça</button></div>
      {!canApprove && <p className="text-xs text-slate-600">A aprovação exige imagem composta e validação atual bem-sucedida.</p>}
      {piece.reviews.length > 0 && <ul className="space-y-1 text-sm">{piece.reviews.map((record) => <li key={record.id}>{new Date(record.created_at).toLocaleString("pt-BR")} · {record.decision} · {record.reviewer_id}{record.comment ? ` · ${record.comment}` : ""}</li>)}</ul>}
    </section>
    {error !== null && <p role="alert" className="text-sm text-red-800">{normalizeHttpError(error).message}</p>}
  </article>
}
