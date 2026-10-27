import { useEffect, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { getRender, startRender } from "@/api/services/campaigns"
import { queryKeys } from "@/api/query-keys"
import { normalizeHttpError } from "@/api/errors"
import type { Piece, RenderRequest, VisualProcessingState } from "@/contracts/api"
import { PiecePreview } from "@/features/campaigns/PiecePreview"

const labels: Record<VisualProcessingState, string> = {
  pending: "Imagem ainda não gerada", processing: "Gerando fundo e compondo…",
  background_ready: "Fundo pronto; compondo peça…", composed: "Composição concluída",
  blocked: "Geração bloqueada", failed: "Falha na geração",
}
const buttonClass = "rounded-lg border border-blue-800 px-3 py-2 text-sm font-semibold text-blue-900 disabled:cursor-not-allowed disabled:opacity-50"

export function PieceVisual({ piece, campaignId, sourcePieces, disabled, onBusyChange }: { piece: Piece; campaignId: string; sourcePieces: Piece[]; disabled: boolean; onBusyChange: (id: string, active: boolean) => void }) {
  const queryClient = useQueryClient()
  const [error, setError] = useState<unknown>(null)
  const [sourcePieceId, setSourcePieceId] = useState("")
  const renderLock = useRef(false)
  const lastRenderAt = useRef(0)
  const previousState = useRef<VisualProcessingState | null>(null)
  const status = useQuery({
    queryKey: queryKeys.render(piece.id), queryFn: () => getRender(piece.id), retry: false,
    refetchInterval: (query) => {
      const state = query.state.data?.visual.state
      return state === "processing" || state === "background_ready" ? 1500 : false
    },
  })
  const renderMutation = useMutation({ mutationFn: (body: RenderRequest) => startRender(piece.id, body), retry: false })
  const visual = status.data?.visual
  const canUseLocal = ["IMAGE_RATE_LIMIT", "IMAGE_QUOTA_EXCEEDED", "IMAGE_UNAVAILABLE", "IMAGE_TIMEOUT", "IMAGE_PROVIDER_UNCONFIGURED"].includes(visual?.error_code ?? "")
  const busy = disabled || visual?.state === "processing" || visual?.state === "background_ready"
  const renderBusy = visual?.state === "processing" || visual?.state === "background_ready" || renderMutation.isPending
  useEffect(() => {
    onBusyChange(piece.id, renderBusy)
    return () => onBusyChange(piece.id, false)
  }, [piece.id, renderBusy, onBusyChange])

  useEffect(() => {
    const state = visual?.state
    if (previousState.current && (previousState.current === "processing" || previousState.current === "background_ready") && state && state !== "processing" && state !== "background_ready") {
      void queryClient.invalidateQueries({ queryKey: queryKeys.campaign(campaignId) })
      void queryClient.invalidateQueries({ queryKey: ["campaigns"] })
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
        void queryClient.invalidateQueries({ queryKey: ["campaigns"] })
      }
    } catch (cause) { setError(cause); lastRenderAt.current = 0 }
    finally { renderLock.current = false }
  }

  return <section className="space-y-5 border-t border-slate-200 pt-5" aria-label="Peça visual">
    {piece.visual_needs_recomposition && <p role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">A peça foi alterada. A prévia anterior foi preservada; recomponha explicitamente e valide novamente antes de solicitar aprovação.</p>}
    {piece.selected_background && <p className="text-sm text-blue-950">Fundo enviado selecionado · {piece.selected_background.width} × {piece.selected_background.height} · SHA-256 {piece.selected_background.sha256.slice(0, 12)}…</p>}
    {status.isPending ? <p role="status">Consultando geração…</p> : status.isError ? <div role="alert">Falha ao consultar renderização: {normalizeHttpError(status.error).message} <button type="button" onClick={() => void status.refetch()} className="underline">Tentar novamente</button></div> : visual && <>
      <section className="space-y-2"><h3 className="font-semibold text-blue-950">Plano visual</h3>
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
        {canUseLocal && <div className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-blue-950"><p>A geração de imagens com IA está temporariamente indisponível. Seus textos e revisões foram preservados. Você pode tentar novamente mais tarde ou compor a peça com fotografia do produto, logo e recursos locais, sem gerar uma nova imagem por IA.</p>{visual.retry_after_seconds != null && <p>Aguarde aproximadamente {visual.retry_after_seconds} segundos antes de tentar novamente o provedor.</p>}<button type="button" className={buttonClass} disabled={busy || renderMutation.isPending} onClick={() => void renderPiece({ use_local_assets: true })}>Criar peça com imagens disponíveis</button></div>}
        {visual.composition_source === "local_assets" && <p className="rounded-lg bg-amber-50 p-3 text-sm font-semibold text-amber-950">Peça produzida com recursos locais · sem geração de imagem por IA</p>}
        {visual.composition_source === "local_test" && <p className="text-sm font-semibold text-amber-950">Imagem demonstrativa local · sem IA real</p>}
        {visual.composition_source === "uploaded" && <p className="rounded-lg bg-blue-50 p-3 text-sm font-semibold text-blue-950">Fundo enviado pela equipe · sem interpretação ou geração de imagem por IA</p>}
        {visual.composition_source === "ai" && <p className="text-sm text-blue-950">Fundo gerado com IA · composição com assets autorizados</p>}
        <div className="flex flex-wrap gap-2">
          <button type="button" className={buttonClass} disabled={!visual.plan || busy || renderMutation.isPending} onClick={() => void renderPiece({})}>Gerar imagem</button>
          <button type="button" className={buttonClass} disabled={!visual.plan || busy || renderMutation.isPending} onClick={() => void renderPiece({ regenerate_background: true })}>Gerar novo fundo</button>
          <button type="button" className={buttonClass} disabled={(!visual.background && !piece.selected_background) || busy || renderMutation.isPending} onClick={() => void renderPiece({ force: true })}>Recompor com fundo existente</button>
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
        {visual.final_image && <PiecePreview pieceId={piece.id} fileId={visual.final_image.file_id} title={piece.title} />}
        {visual.generation && <p className="text-xs text-slate-600">Plano: {visual.generation.provider} · {visual.generation.model}{visual.generation.total_tokens != null ? ` · ${visual.generation.total_tokens} tokens` : ""}</p>}
        {visual.image_generation && <p className="text-xs text-slate-600">Fundo: {visual.image_generation.model} · tentativa {visual.image_generation.attempts}{visual.image_generation.total_tokens != null ? ` · ${visual.image_generation.total_tokens} tokens` : ""}</p>}
      </section>
    </>}
    {(piece.visual_history?.length ?? 0) > 0 && <details className="rounded-lg border border-slate-200 p-3">
      <summary className="cursor-pointer font-semibold text-blue-950">Versões visuais anteriores ({piece.visual_history?.length})</summary>
      {piece.visual_history?.map((previous) => previous.final_image && <HistoricalImage key={previous.final_image.file_id} pieceId={piece.id} fileId={previous.final_image.file_id} date={previous.composed_at} />)}
    </details>}
    {error !== null && <p role="alert" className="text-sm text-red-800">{normalizeHttpError(error).message}</p>}
  </section>
}


function HistoricalImage({ pieceId, fileId, date }: { pieceId: string; fileId: string; date: string | null }) {
  const [open, setOpen] = useState(false)
  return <details className="mt-3" onToggle={(event) => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer text-sm text-blue-900">Versão de {date ? new Date(date).toLocaleString("pt-BR") : fileId}</summary>
    {open && <PiecePreview pieceId={pieceId} fileId={fileId} title="versão anterior" historical />}
  </details>
}
