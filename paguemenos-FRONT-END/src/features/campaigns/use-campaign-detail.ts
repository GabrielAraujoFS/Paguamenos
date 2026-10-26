import { useRef } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { queryKeys } from "@/api/query-keys"
import { getCampaign, reviewPiece, validateCampaign } from "@/api/services/campaigns"
import { normalizeHttpError } from "@/api/errors"
import type { Campaign, ReviewRequest } from "@/contracts/api"

type CampaignAction = { type: "validate" } | { type: "review"; pieceId: string; review: ReviewRequest }

export function useCampaignDetail(id: string) {
  const client = useQueryClient()
  const lock = useRef(false)
  const lastAction = useRef({ key: "", at: 0 })
  const campaign = useQuery({ queryKey: queryKeys.campaign(id), queryFn: () => getCampaign(id), enabled: Boolean(id), retry: false })
  const mutation = useMutation({
    retry: false,
    mutationFn: async (action: CampaignAction) => {
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
  async function runAction(action: CampaignAction) {
    const key = action.type === "validate" ? "validate" : `review:${action.pieceId}:${action.review.decision}`
    if (lock.current || (lastAction.current.key === key && Date.now() - lastAction.current.at < 800)) return
    lastAction.current = { key, at: Date.now() }
    try {
      await mutation.mutateAsync(action)
    } catch (error) {
      lastAction.current = { key: "", at: 0 }
      throw error
    }
  }
  return { campaign, mutation, runAction }
}
