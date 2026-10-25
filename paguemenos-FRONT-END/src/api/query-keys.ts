import type { CampaignListParams } from "@/contracts/api"

export const queryKeys = {
  campaign: (id: string) => ["campaign", id] as const,
  health: ["health"] as const,
  products: ["products"] as const,
  product: (productId: string) => ["products", productId] as const,
  campaigns: (params: CampaignListParams) => ["campaigns", params] as const,
}
