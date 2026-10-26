import { useEffect, useRef, useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { startRender } from "@/api/services/campaigns"
import { queryKeys } from "@/api/query-keys"
import { normalizeHttpError } from "@/api/errors"
import { Button } from "@/components/ui/button"
import type { Piece, RenderRequest, VisualProcessingState } from "@/contracts/api"
import { PiecePreview } from "@/features/campaigns/PiecePreview"
import type { usePieceRender } from "@/features/campaigns/use-piece-render"

const labels: Record<VisualProcessingState, string> = {
  pending: "Imagem ainda não gerada", processing: "Gerando fundo e compondo…",
  background_ready: "Fundo pronto; compondo peça…", composed: "Composição concluída",
  blocked: "Geração bloqueada", failed: "Falha na geração",
}

export function PieceRender({ piece, campaignId, sourcePieces, status }: {
  piece: Piece; campaignId: string; sourcePieces: Piece[]; status: ReturnType<typeof usePieceRender>
}) {
  const client = useQueryClient()
  const [error, setError] = useState<unknown>(null)
  const [sourcePieceId, setSourcePieceId] = useState("")
  const lock = useRef(false)
  const previousState = useRef<VisualProcessingState | null>(null)
  const mutation = useMutation({ mutationFn: (body: RenderRequest) => startRender(piece.id, body), retry: false })
  const visual = status.data?.visual
  const processing = visual?.state === "processing" || visual?.state === "background_ready"

  useEffect(() => {
    const state = visual?.state
    if (previousState.current && (previousState.current === "processing" || previousState.current === "background_ready")
        && state && state !== "processing" && state !== "background_ready") {
      void client.invalidateQueries({ queryKey: queryKeys.campaign(campaignId) })
    }
    if (state) previousState.current = state
  }, [visual?.state, campaignId, client])

  async function render(body: Omit<RenderRequest, "request_id">) {
    if (lock.current || mutation.isPending || processing) return
    lock.current = true
    setError(null)
    try {
      const result = await mutation.mutateAsync({ ...body, request_id: crypto.randomUUID() })
      client.setQueryData(queryKeys.render(piece.id), result)
      if (result.visual.state !== "processing" && result.visual.state !== "background_ready") {
        await client.invalidateQueries({ queryKey: queryKeys.campaign(campaignId) })
      }
    } catch (cause) {
      setError(cause)
    } finally {
      lock.current = false
    }
  }

  return <section className="space-y-4 border-t border-slate-200 pt-5" aria-label="Renderização">
    <h3 className="text-lg font-bold text-blue-950">Imagem da peça</h3>
    {status.isPending ? <p role="status">Consultando geração…</p> : status.isError ?
      <div role="alert" className="text-sm text-red-800">Falha ao consultar renderização: {normalizeHttpError(status.error).message} <button type="button" onClick={() => void status.refetch()} className="underline">Tentar novamente</button></div> : visual && <>
        {visual.plan ? <div className="grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
          <p><strong>Conceito:</strong> {visual.plan.concept || visual.plan.art_direction}</p>
          <p><strong>Estilo:</strong> {visual.plan.visual_style || "Não informado"}</p>
          <p><strong>Cenário:</strong> {visual.plan.scenario || "Não informado"}</p>
          <p><strong>Iluminação:</strong> {visual.plan.lighting || "Não informada"}</p>
          <p><strong>Template:</strong> {visual.template?.name || visual.plan.layout}</p>
          <p><strong>Paleta:</strong> {visual.plan.palette.join(", ") || "Não informada"}</p>
          <p className="sm:col-span-2"><strong>Direção de arte:</strong> {visual.plan.art_direction}</p>
        </div> : <p className="text-sm text-amber-800">Esta campanha não possui plano visual. A geração de imagem requer uma campanha criada com o planejador visual.</p>}
        <p role="status" className="font-semibold text-blue-950">{labels[visual.state]}</p>
        {visual.error_message && <p role="alert" className="text-sm text-red-800">{visual.error_message}{visual.error_code ? ` (${visual.error_code})` : ""}</p>}
        <div className="flex flex-wrap gap-2">
          <Button type="button" disabled={!visual.plan || processing || mutation.isPending} onClick={() => void render({})}>Gerar imagem</Button>
          <Button type="button" variant="outline" disabled={!visual.plan || processing || mutation.isPending} onClick={() => void render({ regenerate_background: true })}>Gerar novo fundo</Button>
          <Button type="button" variant="outline" disabled={!visual.background || processing || mutation.isPending} onClick={() => void render({ force: true })}>Recompor com fundo existente</Button>
        </div>
        {sourcePieces.length > 0 && <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm">Reutilizar fundo de outra peça
            <select value={sourcePieceId} onChange={(event) => setSourcePieceId(event.target.value)} className="mt-1 block rounded-lg border p-2">
              <option value="">Selecione uma peça do mesmo canal</option>
              {sourcePieces.map((source) => <option key={source.id} value={source.id}>{source.title} ({source.id})</option>)}
            </select>
          </label>
          <Button type="button" variant="outline" disabled={!sourcePieceId || processing || mutation.isPending} onClick={() => void render({ source_piece_id: sourcePieceId })}>Usar fundo selecionado</Button>
        </div>}
        {visual.state === "composed" && visual.final_image && <PiecePreview pieceId={piece.id} fileId={visual.final_image.file_id} title={piece.title} />}
        {visual.generation && <p className="text-xs text-slate-600">Plano: {visual.generation.provider} · {visual.generation.model}{visual.generation.total_tokens != null ? ` · ${visual.generation.total_tokens} tokens` : ""}</p>}
        {visual.image_generation && <p className="text-xs text-slate-600">Fundo: {visual.image_generation.model} · tentativa {visual.image_generation.attempts}</p>}
      </>}
    {error !== null && <p role="alert" className="text-sm text-red-800">{normalizeHttpError(error).message}</p>}
  </section>
}
