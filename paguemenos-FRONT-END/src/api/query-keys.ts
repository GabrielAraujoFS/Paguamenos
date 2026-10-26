import type { CampaignListParams } from "@/contracts/api"

export const queryKeys = {
  health: ["health"] as const,
  products: ["products"] as const,
  product: (productId: string) => ["products", productId] as const,
  campaigns: (params: CampaignListParams) => ["campaigns", params] as const,
  campaign: (campaignId: string) => ["campaign", campaignId] as const,
  render: (pieceId: string) => ["render", pieceId] as const,
  pieceImage: (pieceId: string, fileId: string) => ["piece-image", pieceId, fileId] as const,
}
