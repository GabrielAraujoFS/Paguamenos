import { useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, useParams } from "react-router"
import { getCampaign, validateCampaign } from "@/api/services/campaigns"
import { queryKeys } from "@/api/query-keys"
import { normalizeHttpError } from "@/api/errors"
import { LoadingState } from "@/components/shared/RequestState"
import { PieceDetail } from "@/features/campaigns/PieceDetail"

export function CampaignDetailPage() {
  const { campaignId = "" } = useParams()
  const queryClient = useQueryClient()
  const [actionError, setActionError] = useState<unknown>(null)
  const validationLock = useRef(false)
  const lastValidationAt = useRef(0)
  const campaign = useQuery({ queryKey: queryKeys.campaign(campaignId), queryFn: () => getCampaign(campaignId), enabled: Boolean(campaignId), retry: false })
  const validation = useMutation({ mutationFn: () => validateCampaign(campaignId), retry: false })

  async function validate() {
    if (validationLock.current || validation.isPending || Date.now() - lastValidationAt.current < 800) return
    validationLock.current = true
    lastValidationAt.current = Date.now()
    setActionError(null)
    try {
      const result = await validation.mutateAsync()
      queryClient.setQueryData(queryKeys.campaign(campaignId), result)
      void queryClient.invalidateQueries({ queryKey: ["campaigns"] })
    } catch (error) { setActionError(error); lastValidationAt.current = 0 }
    finally { validationLock.current = false }
  }

  return <div className="space-y-6">
    <Link to="/campanhas" className="text-sm font-semibold text-blue-800 underline">Voltar às campanhas</Link>
    {campaign.isPending ? <LoadingState label="Carregando campanha…" /> : campaign.isError ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5">Não foi possível carregar a campanha: {normalizeHttpError(campaign.error).message} <button type="button" onClick={() => void campaign.refetch()} className="underline">Tentar novamente</button></div> : <>
      <header className="space-y-2"><p className="text-sm font-semibold uppercase tracking-widest text-blue-700">Campanha</p>
        <h1 className="text-3xl font-bold text-blue-950">{campaign.data.briefing.campaign_name}</h1>
        <p className="text-slate-600">{campaign.data.briefing.objective}</p><p className="text-sm text-slate-600">Público: {campaign.data.briefing.target_audience}</p>
        <button type="button" onClick={() => void validate()} disabled={validation.isPending} className="rounded-lg bg-blue-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{validation.isPending ? "Validando…" : "Validar campanha"}</button>
        {actionError !== null && <p role="alert" className="text-sm text-red-800">{normalizeHttpError(actionError).message}</p>}
      </header>
      <div className="grid gap-5">{campaign.data.pieces.map((piece) => <PieceDetail key={piece.id} piece={piece} campaignId={campaignId} sourcePieces={campaign.data.pieces.filter((candidate) => candidate.id !== piece.id && candidate.channel === piece.channel)} />)}</div>
    </>}
  </div>
}
