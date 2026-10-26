import { Link } from "react-router"
import type { Campaign, PieceState } from "@/contracts/api"

const stateLabels: Record<PieceState, string> = {
  draft: "Rascunho",
  validated: "Validada",
  approved: "Aprovada",
  rejected: "Rejeitada",
}

const stateClasses: Record<PieceState, string> = {
  draft: "bg-slate-100 text-slate-700",
  validated: "bg-blue-50 text-blue-800",
  approved: "bg-amber-100 text-amber-950",
  rejected: "bg-red-50 text-red-800",
}

const dateFormatter = new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short" })

export function CampaignCard({ campaign }: { campaign: Campaign }) {
  const createdAt = new Date(campaign.created_at)
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="break-words text-lg font-bold text-blue-950">{campaign.briefing.campaign_name}</h2>
          <p className="mt-2 line-clamp-2 text-sm text-slate-600">{campaign.briefing.objective}</p>
        </div>
        <p className="shrink-0 text-xs text-slate-500">{Number.isNaN(createdAt.getTime()) ? "Data indisponível" : dateFormatter.format(createdAt)}</p>
      </div>
      <div className="mt-5 border-t border-slate-100 pt-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{campaign.pieces.length} {campaign.pieces.length === 1 ? "peça" : "peças"}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {campaign.pieces.map((piece) => (
            <span key={piece.id} className={`rounded-full px-3 py-1 text-xs font-semibold ${stateClasses[piece.state]}`}>
              {piece.channel} · {stateLabels[piece.state]}
            </span>
          ))}
        </div>
      </div>
      <Link to={`/campanhas/${encodeURIComponent(campaign.id)}`} className="mt-4 inline-block text-sm font-semibold text-blue-800 underline">Abrir campanha</Link>
    </article>
  )
}
