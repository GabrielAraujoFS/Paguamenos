import { useState, type FormEvent } from "react"
import { Link } from "react-router"
import { normalizeHttpError } from "@/api/errors"
import { EmptyState, LoadingState } from "@/components/shared/RequestState"
import type { PieceState } from "@/contracts/api"
import { CampaignCard } from "@/features/campaigns/CampaignCard"
import { useCampaigns } from "@/features/campaigns/use-campaigns"

const pageSize = 20
const fieldClass = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-950 outline-none focus-visible:border-blue-700 focus-visible:ring-2 focus-visible:ring-blue-700/20"
const actionClass = "rounded-lg border border-blue-900 px-4 py-2.5 text-sm font-semibold text-blue-950 hover:bg-blue-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700 disabled:cursor-not-allowed disabled:opacity-50"

export function CampaignsPage() {
  const [searchInput, setSearchInput] = useState("")
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState<PieceState | "">("")
  const [page, setPage] = useState(1)
  const campaigns = useCampaigns({ page, page_size: pageSize, ...(search ? { search } : {}), ...(status ? { status } : {}) })
  const hasFilters = Boolean(search || status)

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPage(1)
    setSearch(searchInput.trim())
  }

  function clearFilters() {
    setSearchInput("")
    setSearch("")
    setStatus("")
    setPage(1)
  }

  return (
    <div className="space-y-7">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-widest text-blue-700">Campanhas</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-blue-950">Campanhas</h1>
          <p className="mt-2 text-sm text-slate-600">Gerencie e acompanhe suas campanhas de marketing em um só lugar.</p>
        </div>
        <Link to="/campaigns/new" className="inline-flex w-fit rounded-lg bg-blue-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700">Nova campanha</Link>
      </div>

      <form onSubmit={submitSearch} className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-[minmax(0,1fr)_minmax(160px,220px)_auto] sm:items-end sm:p-5" role="search">
        <div>
          <label htmlFor="campaign-search" className="mb-1.5 block text-sm font-semibold text-blue-950">Pesquisar pelo nome</label>
          <input id="campaign-search" type="search" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} className={fieldClass} placeholder="Nome da campanha" />
        </div>
        <div>
          <label htmlFor="campaign-status" className="mb-1.5 block text-sm font-semibold text-blue-950">Estado da peça</label>
          <select id="campaign-status" value={status} onChange={(event) => { setStatus(event.target.value as PieceState | ""); setPage(1) }} className={fieldClass}>
            <option value="">Todos os estados</option>
            <option value="draft">Rascunho</option>
            <option value="validated">Validada</option>
            <option value="approved">Aprovada</option>
            <option value="rejected">Rejeitada</option>
          </select>
        </div>
        <button type="submit" className={actionClass}>Pesquisar</button>
      </form>

      {campaigns.isPending ? <LoadingState label="Carregando campanhas…" /> : campaigns.isError ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-950" role="alert">
          <p className="font-semibold">Não foi possível carregar as campanhas</p>
          <p className="mt-1">{campaigns.error instanceof Error && campaigns.error.message === "Resposta inesperada da listagem de campanhas." ? campaigns.error.message : normalizeHttpError(campaigns.error).message}</p>
          <button type="button" onClick={() => void campaigns.refetch()} className="mt-4 rounded-lg border border-red-300 px-3 py-2 font-medium hover:bg-red-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-700">Tentar novamente</button>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-600" role="status">{campaigns.data.total} {campaigns.data.total === 1 ? "campanha encontrada" : "campanhas encontradas"}{hasFilters ? " com os filtros atuais" : ""}</p>
            <button type="button" onClick={() => void campaigns.refetch()} disabled={campaigns.isFetching} className={actionClass}>{campaigns.isFetching ? "Atualizando…" : "Atualizar lista"}</button>
          </div>
          {campaigns.data.items.length === 0 ? (
            <div className="space-y-3">
              <EmptyState title={hasFilters ? "Nenhuma campanha corresponde à pesquisa" : "Nenhuma campanha encontrada"}>
                {hasFilters ? "Altere a busca ou o estado selecionado." : "Crie uma campanha para começar a acompanhar suas peças."}
              </EmptyState>
              {hasFilters && <button type="button" onClick={clearFilters} className={actionClass}>Limpar filtros</button>}
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {campaigns.data.items.map((campaign) => <CampaignCard key={campaign.id} campaign={campaign} />)}
            </div>
          )}
          {campaigns.data.total_pages > 1 && (
            <nav aria-label="Páginas de campanhas" className="flex items-center justify-center gap-4">
              <button type="button" onClick={() => setPage((current) => current - 1)} disabled={page <= 1} className={actionClass}>Anterior</button>
              <span className="text-sm text-slate-600">Página {campaigns.data.page} de {campaigns.data.total_pages}</span>
              <button type="button" onClick={() => setPage((current) => current + 1)} disabled={page >= campaigns.data.total_pages} className={actionClass}>Próxima</button>
            </nav>
          )}
        </>
      )}
    </div>
  )
}
