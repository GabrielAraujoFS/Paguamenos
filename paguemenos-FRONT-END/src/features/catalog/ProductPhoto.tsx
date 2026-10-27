import { useState } from "react"
import { ImageOff } from "lucide-react"
import type { Product } from "@/contracts/api"
import { getProductImageUrl } from "@/api/services/products"

export function ProductPhoto({ product }: { product: Pick<Product, "id" | "name"> }) {
  const [unavailable, setUnavailable] = useState(false)
  return <div className="mb-5 flex aspect-[4/3] w-full items-center justify-center overflow-hidden rounded-lg border border-slate-100 bg-slate-50 p-2">
    {unavailable ? <div role="img" aria-label={`Fotografia indisponível de ${product.name}`} className="flex flex-col items-center gap-2 text-sm text-slate-500">
      <ImageOff className="size-8" aria-hidden="true" /><span>Fotografia indisponível</span>
    </div> : <img src={getProductImageUrl(product.id)} alt={`Fotografia do produto ${product.name}`} loading="lazy" decoding="async" className="h-full w-full object-contain" onError={() => setUnavailable(true)} />}
  </div>
}
