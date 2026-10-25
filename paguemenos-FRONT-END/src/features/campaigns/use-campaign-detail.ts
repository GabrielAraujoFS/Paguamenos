import { useRef } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/api/query-keys"
import { getCampaign, reviewPiece, validateCampaign } from "@/api/services/campaigns"
import { normalizeHttpError } from "@/api/errors"
import type { Campaign, ReviewRequest } from "@/contracts/api"

export function useCampaignDetail(id: string) {
  const client = useQueryClient()
  const lock = useRef(false)
  const campaign = useQuery({ queryKey: queryKeys.campaign(id), queryFn: () => getCampaign(id), enabled: Boolean(id), retry: false })
  const mutation = useMutation({
    retry: false,
    mutationFn: async (action: { type: "validate" } | { type: "review"; pieceId: string; review: ReviewRequest }) => {
      if (lock.current) throw new Error("Uma operação já está em andamento.")
      lock.current = true
      try {
        await client.cancelQueries({ queryKey: queryKeys.campaign(id) })
        if (action.type === "validate") {
          client.setQueryData(queryKeys.campaign(id), await validateCampaign(id))
        } else {
          const piece = await reviewPiece(action.pieceId, action.review)
          client.setQueryData<Campaign>(queryKeys.campaign(id), (current) => current && ({
            ...current, pieces: current.pieces.map((entry) => entry.id === piece.id ? piece : entry),
          }))
        }
      } catch (error) {
        if (normalizeHttpError(error).status === 409) {
          // A conflict may have invalidated the piece on the server.
          try {
            await client.fetchQuery({ queryKey: queryKeys.campaign(id), queryFn: () => getCampaign(id), retry: false, staleTime: 0 })
          } catch {
            // The query error hides stale actions until an explicit refresh succeeds.
          }
        }
        throw error
      } finally {
        lock.current = false
        void client.invalidateQueries({ queryKey: ["campaigns"] })
      }
    },
  })
  return { campaign, mutation }
}
