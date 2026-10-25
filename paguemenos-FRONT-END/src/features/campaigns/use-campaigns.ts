import { useQuery } from "@tanstack/react-query"
import { queryKeys } from "@/api/query-keys"
import { getCampaigns } from "@/api/services/campaigns"
import type { CampaignListParams } from "@/contracts/api"

export function useCampaigns(params: CampaignListParams) {
  return useQuery({ queryKey: queryKeys.campaigns(params), queryFn: () => getCampaigns(params) })
}
