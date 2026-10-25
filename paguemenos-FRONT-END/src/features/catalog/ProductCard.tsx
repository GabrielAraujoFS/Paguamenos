import { ArrowUpRight } from "lucide-react"
import { Link } from "react-router"
import type { Product } from "@/contracts/api"
import { formatPrice } from "@/features/catalog/format-price"

export function ProductCard({ product }: { product: Product }) {
  return (
    <article className="flex h-full flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">{product.category}</p>
          <h2 className="mt-2 text-lg font-semibold text-blue-950">{product.name}</h2>
        </div>
        <span className="shrink-0 rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-900">{formatPrice(product.price)}</span>
      </div>
      <p className="mt-3 flex-1 text-sm leading-relaxed text-slate-600">{product.description}</p>
      <Link to={`/products/${encodeURIComponent(product.id)}`} className="mt-6 inline-flex w-fit items-center gap-1 text-sm font-semibold text-blue-800 underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700">
        Ver produto <ArrowUpRight className="size-4" aria-hidden="true" />
      </Link>
    </article>
  )
}
