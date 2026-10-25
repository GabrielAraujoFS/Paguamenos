import { apiClient } from "@/api/client"
import type { Product } from "@/contracts/api"

export async function getProducts(): Promise<Product[]> {
  const { data } = await apiClient.get<Product[]>("/products")
  return data
}

export async function getProduct(productId: string): Promise<Product> {
  const { data } = await apiClient.get<Product>(`/products/${encodeURIComponent(productId)}`)
  return data
}
