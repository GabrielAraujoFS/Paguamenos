import { ArrowLeft } from "lucide-react"
import { Link, useParams } from "react-router"
import { EmptyState, ErrorState, LoadingState } from "@/components/shared/RequestState"
import { normalizeHttpError } from "@/api/errors"
import { formatPrice } from "@/features/catalog/format-price"
import { useProduct } from "@/features/catalog/use-products"

export function ProductDetailPage() {
  const { productId } = useParams<{ productId: string }>()
  const product = useProduct(productId)
  const error = product.isError ? normalizeHttpError(product.error) : null

  return (
    <div className="space-y-6">
      <Link to="/products" className="inline-flex items-center gap-2 text-sm font-semibold text-blue-800 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700"><ArrowLeft className="size-4" aria-hidden="true" /> Voltar ao catálogo</Link>
      {product.isPending ? <LoadingState label="Carregando produto…" /> : error?.status === 404 ? (
        <EmptyState title="Produto não encontrado">Confira o endereço ou volte ao catálogo.</EmptyState>
      ) : product.isError ? (
        <ErrorState error={product.error} onRetry={() => void product.refetch()} />
      ) : (
        <article className="max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-9">
          <p className="text-sm font-semibold uppercase tracking-widest text-blue-700">{product.data.category}</p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight text-blue-950">{product.data.name}</h1>
          <p className="mt-5 leading-relaxed text-slate-700">{product.data.description}</p>
          <dl className="mt-8 grid gap-5 border-t border-slate-200 pt-6 sm:grid-cols-2">
            <div><dt className="text-sm text-slate-500">Preço</dt><dd className="mt-1 text-xl font-semibold text-blue-950">{formatPrice(product.data.price)}</dd></div>
            <div><dt className="text-sm text-slate-500">Oferta autorizada</dt><dd className="mt-1 text-sm leading-relaxed text-slate-800">{product.data.authorized_offer}</dd></div>
          </dl>
          <Link to={`/campaigns/new?product_id=${encodeURIComponent(product.data.id)}`} className="mt-8 inline-flex rounded-lg bg-blue-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700">Criar briefing com este produto</Link>
        </article>
      )}
    </div>
  )
}
