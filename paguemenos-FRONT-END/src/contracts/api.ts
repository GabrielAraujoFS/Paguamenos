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
  generation?: GenerationMetadata | null
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

export type VisualProcessingState = "pending" | "processing" | "background_ready" | "composed" | "blocked" | "failed"

export interface ImageReference {
  file_id: string
  media_type: "image/png" | "image/jpeg" | "image/webp"
  width: number | null
  height: number | null
  sha256: string
}

export interface VisualPlan {
  channel: Channel
  art_direction: string
  background_prompt: string
  layout: string
  palette: string[]
  concept: string | null
  visual_style: string | null
  scenario: string | null
  lighting: string | null
  decorative_elements: string[]
}

export interface TemplateConfig {
  name: string
  channel: Channel
  width: number
  height: number
  safe_area: Record<string, number>
  min_font_size: number
  max_font_size: number
}

export interface GenerationMetadata {
  provider: string
  model: string
  created_at: string
  prompt_tokens: number | null
  response_tokens: number | null
  total_tokens: number | null
  attempts: number | null
}

export interface BackgroundGenerationMetadata {
  generation_id: string
  plan_id: string
  model: string
  prompt: string
  created_at: string
  attempts: number
  duration_seconds: number
  prompt_tokens: number | null
  response_tokens: number | null
  total_tokens: number | null
  estimated_cost_usd: string | null
  cost_basis: string | null
}

export interface VisualMetadata {
  composition_source?: "ai" | "local_assets" | "local_test" | null
  fallback_reason?: string | null
  retry_after_seconds?: number | null
  state: VisualProcessingState
  plan: VisualPlan | null
  template: TemplateConfig | null
  background: ImageReference | null
  product_image: ImageReference | null
  final_image: ImageReference | null
  generation: GenerationMetadata | null
  render_request_id: string | null
  plan_id: string | null
  image_generation: BackgroundGenerationMetadata | null
  composed_at: string | null
  source_piece_id: string | null
  error_code: string | null
  error_message: string | null
  visual_review_required: boolean
}

export interface RenderStatus {
  piece_id: string
  visual: VisualMetadata
}

export interface RenderRequest {
  use_local_assets?: boolean
  request_id?: string
  source_piece_id?: string
  regenerate_background?: boolean
  force?: boolean
}

export interface ReviewRequest {
  decision: Decision
  reviewer_id: string
  comment?: string | null
}

export interface ApiErrorResponse {
  error: {
    code: string
    message: string
    details: Array<Record<string, unknown>>
  }
}
