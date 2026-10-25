import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/api/query-keys"
import { getProduct, getProducts } from "@/api/services/products"

export function useProducts() {
  return useQuery({ queryKey: queryKeys.products, queryFn: getProducts })
}

export function useProduct(productId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.product(productId ?? ""),
    queryFn: () => getProduct(productId!),
    enabled: Boolean(productId),
  })
}
