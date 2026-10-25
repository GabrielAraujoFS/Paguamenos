export interface Health {
  status: string
  generation_provider: string
}

export interface Product {
  id: string
  name: string
  description: string
  category: string
  price: string
  authorized_offer: string
}

export type Channel = "feed" | "story" | "banner"
export type PieceState = "draft" | "validated" | "approved" | "rejected"
export type Severity = "info" | "warning" | "critical"
export type Decision = "approved" | "rejected"

export interface Briefing {
  campaign_name: string
  product_id: string
  objective: string
  target_audience: string
  channels: Channel[]
  additional_instructions: string | null
}

export type GenerateRequest = Omit<Briefing, "additional_instructions"> & {
  additional_instructions?: string | null
}

export interface ValidationResult {
  rule_code: string
  severity: Severity
  message: string
  field: string
  passed: boolean
}

export interface ValidationRun {
  id: string
  created_at: string
  fingerprint: string
  success: boolean
  results: ValidationResult[]
}

export interface ReviewRecord {
  id: string
  created_at: string
  fingerprint: string
  decision: Decision
  reviewer_id: string
  comment: string | null
}

export interface Piece {
  id: string
  campaign_id: string
  channel: Channel
  title: string
  subtitle: string
  cta: string
  disclaimer: string
  product_id: string
  product_name: string
  price: string
  authorized_offer: string
  state: PieceState
  validations: ValidationRun[]
  reviews: ReviewRecord[]
}

export interface Campaign {
  id: string
  created_at: string
  briefing: Briefing
  pieces: Piece[]
}

export interface CampaignPage {
  items: Campaign[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface CampaignListParams {
  page: number
  page_size: number
  search?: string
  status?: PieceState
}

export interface ApiErrorResponse {
  error: {
    code: string
    message: string
    details: Array<Record<string, unknown>>
  }
}
