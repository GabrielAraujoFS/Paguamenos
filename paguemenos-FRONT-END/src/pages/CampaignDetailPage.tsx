import { useState } from "react"
import { Link, useParams } from "react-router"
import { normalizeHttpError } from "@/api/errors"
import { ErrorState, LoadingState } from "@/components/shared/RequestState"
import { Button } from "@/components/ui/button"
import { PieceDetail } from "@/features/campaigns/PieceDetail"
import { useCampaignDetail } from "@/features/campaigns/use-campaign-detail"

export function CampaignDetailPage() {
  const { campaignId = "" } = useParams()
  const { campaign, mutation } = useCampaignDetail(campaignId)
  const [notice, setNotice] = useState("")
  const busy = mutation.isPending || campaign.isFetching
  const data = campaign.data
  const error = mutation.isError ? normalizeHttpError(mutation.error) : null
  return <div className="space-y-7">
    <Link to="/campanhas" className="text-sm font-semibold text-blue-800 hover:underline">← Voltar às campanhas</Link>
    {campaign.isPending ? <LoadingState label="Carregando campanha…" /> : campaign.isError ? <ErrorState error={campaign.error} onRetry={() => void campaign.refetch()} /> : data && <>
      <header className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-widest text-blue-700">Campanha</p>
        <h1 className="break-words text-3xl font-bold text-blue-950">{data.briefing.campaign_name}</h1>
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          {[["Objetivo", data.briefing.objective], ["Público-alvo", data.briefing.target_audience], ["Produto", data.pieces[0]?.product_name ?? data.briefing.product_id], ["Canais", data.briefing.channels.join(", ")], ["Identificador da campanha", data.id], ["Data de criação", new Date(data.created_at).toLocaleString("pt-BR")]].map(([label, value]) => <div key={label} className="min-w-0"><dt className="font-semibold text-blue-950">{label}</dt><dd className="mt-1 whitespace-pre-wrap break-words text-slate-700">{value}</dd></div>)}
        </dl>
        <p className="text-sm text-slate-600">Validar campanha acrescenta uma execução ao histórico de cada peça. A aprovação continua sendo uma decisão humana por peça.</p>
        <div className="flex flex-wrap gap-3">
          <Button disabled={busy} onClick={async () => { setNotice(""); try { await mutation.mutateAsync({ type: "validate" }); setNotice("Validação concluída. Consulte os resultados do Brand Guardian em cada peça.") } catch { /* Error shown below; no automatic retry. */ } }}> {mutation.isPending ? "Processando…" : "Validar campanha"}</Button>
          <Button variant="outline" disabled={busy} onClick={() => { setNotice(""); mutation.reset(); void campaign.refetch() }}>Atualizar campanha</Button>
        </div>
      </header>
      {data.pieces.map((piece) => <PieceDetail key={`${data.id}-${piece.id}`} piece={piece} campaignId={data.id} sourcePieces={data.pieces.filter((candidate) => candidate.id !== piece.id && candidate.channel === piece.channel)} busy={busy} onReview={async (pieceId, review) => { setNotice(""); try { await mutation.mutateAsync({ type: "review", pieceId, review }); setNotice("Revisão registrada. O estado da peça foi atualizado."); return true } catch { return false } }} />)}
    </>}
    {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-950"><p className="font-semibold">Não foi possível concluir a operação</p><p className="mt-1">{error.message}</p>{error.status === 409 && <p className="mt-2">A aprovação foi bloqueada. Confira o estado atualizado e valide novamente se necessário.</p>}{error.kind === "network" && <p className="mt-2">A resposta não foi confirmada. Atualize a campanha antes de repetir a operação para evitar registros duplicados.</p>}</div>}
    {notice && <p role="status" className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950">{notice}</p>}
  </div>
}
