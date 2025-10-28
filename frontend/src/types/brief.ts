/**
 * TypeScript types for Project Brief and related models.
 * Mirrors the Python Pydantic models from the backend.
 */

export interface CustomerPersona {
  name: string
  age_range: string
  description: string
  pain_points: string[]
  motivations: string[]
  product_usage_context: string
}

export interface ImageAsset {
  asset_id: string
  url: string
  generation_params: Record<string, any>
  description: string
}

export interface PlanPhase {
  phase_number: number
  agent: string
  task_description: string
  dependencies: number[]
}

export interface CampaignPlan {
  phases: PlanPhase[]
  approval_status: 'pending' | 'approved' | 'rejected'
  description: string
}

export interface ProjectBrief {
  // Identifiers
  project_id: string
  session_id: string

  // Campaign basics (PRODUCT-AGNOSTIC)
  product_name: string
  product_category: string
  theme: string
  key_features: string[]
  brand_tone: string
  target_market: string
  initial_sketch_url?: string

  // Strategy outputs
  personas: CustomerPersona[]
  slogans: string[]
  selected_slogan?: string

  // Art outputs
  hero_images: ImageAsset[]
  selected_image?: ImageAsset

  // Execution plan
  campaign_plan?: CampaignPlan
  plan_approved: boolean

  // Asset tracking
  completed_assets: Record<string, any>

  // Metadata
  version: number
  created_at: string
  updated_at: string
  status: 'planning' | 'executing' | 'completed'
}

export interface ConversationMessage {
  role: 'user' | 'assistant'
  text: string
  timestamp: string
  is_partial?: boolean
}

export interface WebSocketMessage {
  type: string
  [key: string]: any
}
