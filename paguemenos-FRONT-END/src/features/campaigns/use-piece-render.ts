import { useQuery } from "@tanstack/react-query"
import { getRender } from "@/api/services/campaigns"
import { queryKeys } from "@/api/query-keys"

export function usePieceRender(pieceId: string) {
  return useQuery({
    queryKey: queryKeys.render(pieceId), queryFn: () => getRender(pieceId), retry: false,
    refetchInterval: (query) => {
      const state = query.state.data?.visual.state
      return state === "processing" || state === "background_ready" ? 1500 : false
    },
  })
}
