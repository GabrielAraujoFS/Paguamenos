import { apiClient } from "@/api/client"
import type { Health } from "@/contracts/api"

export async function getHealth(): Promise<Health> {
  const { data } = await apiClient.get<Health>("/health")
  return data
}

