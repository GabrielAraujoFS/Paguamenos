import { useSearchParams } from "react-router"
import { EmptyState, ErrorState, LoadingState } from "@/components/shared/RequestState"
import { BriefingForm } from "@/features/campaigns/BriefingForm"
import { useProducts } from "@/features/catalog/use-products"

export function NewCampaignPage() {
  const [searchParams] = useSearchParams()
  const products = useProducts()

  return (
    <div className="space-y-7">
      <div>
        <p className="text-sm font-semibold uppercase tracking-widest text-blue-700">Nova campanha</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-blue-950">Preencha o briefing</h1>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">Selecione um produto do catálogo e descreva a campanha. O backend gera uma peça para cada canal escolhido.</p>
      </div>
      {products.isPending ? <LoadingState label="Carregando produtos…" /> : products.isError ? (
        <ErrorState error={products.error} onRetry={() => void products.refetch()} />
      ) : products.data.length === 0 ? (
        <EmptyState title="Não há produtos disponíveis">O briefing precisa de um produto do catálogo. Tente novamente quando o backend tiver produtos.</EmptyState>
      ) : (
        <BriefingForm products={products.data} initialProductId={searchParams.get("product_id") ?? undefined} />
      )}
    </div>
  )
}
