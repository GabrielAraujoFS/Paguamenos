import { apiClient } from "@/api/client"
import type { Campaign, CampaignListParams, CampaignPage, GenerateRequest, Piece, PieceEditRequest, RenderRequest, RenderStatus, ReviewRequest } from "@/contracts/api"

function isCampaignPage(value: unknown): value is CampaignPage {
  if (typeof value !== "object" || value === null) return false
  const page = value as Record<string, unknown>
  return Array.isArray(page.items) && page.items.every((item: unknown) => {
    if (typeof item !== "object" || item === null) return false
    const campaign = item as Record<string, unknown>
    if (typeof campaign.briefing !== "object" || campaign.briefing === null) return false
    const briefing = campaign.briefing as Record<string, unknown>
    return typeof campaign.id === "string" && typeof campaign.created_at === "string" &&
      typeof briefing.campaign_name === "string" && typeof briefing.objective === "string" &&
      Array.isArray(campaign.pieces) && campaign.pieces.every((piece: unknown) => {
        if (typeof piece !== "object" || piece === null) return false
        const entry = piece as Record<string, unknown>
        return typeof entry.id === "string" &&
          (entry.channel === "feed" || entry.channel === "story" || entry.channel === "banner") &&
          (entry.state === "draft" || entry.state === "validated" || entry.state === "approved" || entry.state === "rejected")
      })
  }) && ["total", "page", "page_size", "total_pages"].every((key) =>
    Number.isInteger(page[key]) && (page[key] as number) >= 0,
  )
}

export async function getCampaigns(params: CampaignListParams): Promise<CampaignPage> {
  const { data } = await apiClient.get<unknown>("/campaigns", { params })
  if (!isCampaignPage(data)) throw new Error("Resposta inesperada da listagem de campanhas.")
  return data
}

export async function generateCampaign(briefing: GenerateRequest): Promise<Campaign> {
  const { data } = await apiClient.post<Campaign>("/campaigns/generate", briefing, {
    headers: { "Content-Type": "application/json" },
  })
  return data
}

export async function generateDemonstration(briefing: GenerateRequest, token: string): Promise<Campaign> {
  return (await apiClient.post<Campaign>("/campaigns/generate", briefing, { params: { demo_token: token } })).data
}

export async function getCampaign(campaignId: string): Promise<Campaign> {
  const { data } = await apiClient.get<Campaign>(`/campaigns/${encodeURIComponent(campaignId)}`)
  return data
}

export async function validateCampaign(campaignId: string): Promise<Campaign> {
  const { data } = await apiClient.post<Campaign>(`/campaigns/${encodeURIComponent(campaignId)}/validate`)
  return data
}

export async function reviewPiece(pieceId: string, request: ReviewRequest): Promise<Piece> {
  const { data } = await apiClient.post<Piece>(`/pieces/${encodeURIComponent(pieceId)}/review`, request)
  return data
}

export async function startRender(pieceId: string, request: RenderRequest): Promise<RenderStatus> {
  const { data } = await apiClient.post<RenderStatus>(`/pieces/${encodeURIComponent(pieceId)}/render`, request)
  return data
}

export async function getRender(pieceId: string): Promise<RenderStatus> {
  const { data } = await apiClient.get<RenderStatus>(`/pieces/${encodeURIComponent(pieceId)}/render`)
  return data
}

export async function getPieceImage(pieceId: string, versionId?: string): Promise<Blob> {
  const { data } = await apiClient.get<Blob>(`/pieces/${encodeURIComponent(pieceId)}/image`, {
    ...(versionId ? { params: { version_id: versionId } } : {}), responseType: "blob", headers: { Accept: "image/png" },
  })
  return data
}


export async function editPiece(pieceId: string, request: PieceEditRequest): Promise<Piece> {
  return (await apiClient.post<Piece>(`/pieces/${encodeURIComponent(pieceId)}/edit`, request)).data
}

export async function uploadPieceBackground(pieceId: string, file: File, editorId: string, expectedVersion: number): Promise<Piece> {
  return (await apiClient.post<Piece>(`/pieces/${encodeURIComponent(pieceId)}/background`, file, {
    params: { editor_id: editorId, expected_version: expectedVersion, rights_confirmed: true },
    headers: { "Content-Type": file.type },
  })).data
}
