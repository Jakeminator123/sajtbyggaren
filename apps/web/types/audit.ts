/**
 * TypeScript types for Site Audit feature
 * Based on sajtstudio's audit implementation
 */

export type AuditMode = "basic" | "advanced";

// Improvement suggestion with impact and effort assessment
export interface Improvement {
  item: string;
  impact: "high" | "medium" | "low";
  effort: "low" | "medium" | "high";
  why?: string;
  how?: string;
  estimated_time?: string;
  technologies?: string[];
  code_example?: string;
  category?: "UX" | "Tech" | "Content" | "Marketing" | "Security";
}

// Technical recommendation with implementation details
export interface TechnicalRecommendation {
  area: string;
  current_state: string;
  recommendation: string;
  implementation?: string;
}

// Security analysis results
export interface SecurityAnalysis {
  https_status: string;
  headers_analysis: string;
  cookie_policy: string;
  vulnerabilities?: string[];
}

// Budget estimate breakdown
export interface BudgetEstimate {
  low?: number;
  high?: number;
  immediate_fixes?: { low: number; high: number };
  full_optimization?: { low: number; high: number };
  ongoing_monthly?: { low: number; high: number };
  initial_development?: { low: number; high: number };
  annual_maintenance?: { low: number; high: number };
  marketing_launch?: { low: number; high: number };
  currency: string;
  payment_structure?: string;
}

// Competitor insights
export interface CompetitorInsights {
  industry_standards: string;
  missing_features: string;
  unique_strengths: string;
}

// Competitor benchmarking
export interface CompetitorBenchmarking {
  industry_leaders?: string[];
  common_features?: string[];
  differentiation_opportunities?: string[];
}

// Business profile (advanced)
export interface BusinessProfile {
  industry: string;
  company_size: string;
  business_model: string;
  maturity: string;
  core_offers: string[];
  revenue_streams: string[];
}

// Market context (advanced)
export interface MarketContext {
  primary_geography: string;
  service_area: string;
  competition_level: string;
  key_competitors: string[];
  seasonal_patterns: string;
  local_market_dynamics: string;
}

// Customer segmentation (advanced)
export interface CustomerSegments {
  primary_segment: string;
  secondary_segments: string[];
  customer_needs: string[];
  decision_triggers: string[];
  trust_signals: string[];
}

// Competitive landscape (advanced)
export interface CompetitiveLandscape {
  positioning: string;
  differentiation: string;
  price_positioning: string;
  barriers_to_entry: string;
  opportunities: string[];
}

// Target audience analysis
export interface TargetAudienceAnalysis {
  demographics: string;
  behaviors: string;
  pain_points: string;
  expectations: string;
}

// Content strategy
export interface ContentStrategy {
  key_pages?: string[];
  content_types?: string[];
  seo_foundation?: string;
  conversion_paths?: string[];
}

// Design direction
export interface DesignDirection {
  style: string;
  color_psychology: string;
  ui_patterns?: string[];
  accessibility_level: string;
}

// Technical architecture
export interface TechnicalArchitecture {
  recommended_stack?: {
    frontend?: string;
    backend?: string;
    cms?: string;
    hosting?: string;
    [key: string]: string | undefined;
  };
  integrations?: string[];
  security_measures?: string[];
}

// Implementation roadmap phase
export interface RoadmapPhase {
  duration?: string;
  deliverables?: string[];
  activities?: string[];
}

// Implementation roadmap
export interface ImplementationRoadmap {
  phase_1?: RoadmapPhase;
  phase_2?: RoadmapPhase;
  phase_3?: RoadmapPhase;
  launch?: RoadmapPhase;
  [key: string]: RoadmapPhase | undefined;
}

// Success metrics
export interface SuccessMetrics {
  kpis?: string[];
  tracking_setup?: string;
  review_schedule?: string;
}

// Priority matrix for improvements
export interface PriorityMatrix {
  quick_wins?: string[];
  major_projects?: string[];
  fill_ins?: string[];
  thankless_tasks?: string[];
}

// Extracted site content for template generation
export interface SiteContentExtraction {
  // Company/business info
  company_name: string;
  tagline?: string;
  description: string;
  industry: string;
  location?: string;

  // What they offer
  services?: string[];
  products?: string[];
  unique_selling_points?: string[];

  // Page sections found
  sections: {
    name: string;
    content: string;
    type:
      | "hero"
      | "services"
      | "about"
      | "contact"
      | "testimonials"
      | "portfolio"
      | "pricing"
      | "faq"
      | "team"
      | "cta"
      | "footer"
      | "other";
  }[];

  // Call to actions
  ctas?: string[];

  // Contact info
  contact?: {
    email?: string;
    phone?: string;
    address?: string;
    social_links?: string[];
  };
}

// Color theme extraction
export interface ColorThemeExtraction {
  primary_color: string; // Main brand color (hex)
  secondary_color?: string; // Secondary color (hex)
  accent_color?: string; // Accent/CTA color (hex)
  background_color: string; // Main background (hex)
  text_color: string; // Main text color (hex)

  // Overall style
  theme_type: "light" | "dark" | "mixed";
  style_description: string; // e.g. "Minimalistisk, modern, professionell"

  // Design characteristics
  design_style?:
    | "minimalist"
    | "bold"
    | "playful"
    | "corporate"
    | "creative"
    | "elegant"
    | "tech"
    | "organic";
  typography_style?: string; // e.g. "Sans-serif, clean, modern"
}

// Ready-to-use prompt for template generation
export interface TemplateGenerationData {
  // Super prompt for v0/AI generation
  generation_prompt: string;

  // Key features to include
  must_have_sections: string[];

  // Style guidelines
  style_notes: string;

  // Suggested improvements over original
  improvements_to_apply: string[];
}

// Audit scores (0-100 for each category)
export interface AuditScores {
  seo?: number;
  technical_seo?: number;
  ux?: number;
  content?: number;
  performance?: number;
  accessibility?: number;
  security?: number;
  mobile?: number;
  [key: string]: number | undefined;
}

// Cost information
export interface AuditCost {
  tokens: number;
  sek: number;
  usd: number;
}

// Scrape/debug metadata (helps explain data quality in the report)
export interface ScrapeSummary {
  sampled_urls: string[];
  pages_sampled: number;
  aggregated_word_count: number;
  word_count_source?: "scraper" | "ai_estimate";
  headings_count: number;
  images_count: number;
  response_time_ms: number;
  is_js_rendered: boolean;
  web_search_calls?: number;
  notes?: string[];
}

// Main audit result type
export interface AuditResult {
  // Type of audit
  audit_type: "website_audit" | "recommendation";
  audit_mode?: AuditMode;

  // Basic info
  company?: string;
  domain?: string;
  timestamp?: string;

  // Scores (for website audit)
  audit_scores?: AuditScores;

  // Findings
  strengths?: string[];
  issues?: string[];
  improvements?: Improvement[];

  // Budget and outcomes
  budget_estimate?: BudgetEstimate;
  expected_outcomes?: string[];

  // For recommendation mode
  website_type_recommendation?: string;

  // Technical analysis
  security_analysis?: SecurityAnalysis;
  technical_recommendations?: TechnicalRecommendation[];
  technical_architecture?: TechnicalArchitecture;

  // Business analysis
  competitor_insights?: CompetitorInsights;
  competitor_benchmarking?: CompetitorBenchmarking;
  target_audience_analysis?: TargetAudienceAnalysis;
  business_profile?: BusinessProfile;
  market_context?: MarketContext;
  customer_segments?: CustomerSegments;
  competitive_landscape?: CompetitiveLandscape;

  // Strategy
  content_strategy?: ContentStrategy;
  design_direction?: DesignDirection;
  priority_matrix?: PriorityMatrix;

  // Planning
  implementation_roadmap?: ImplementationRoadmap;
  success_metrics?: SuccessMetrics;

  // NEW: Extracted site content for template generation
  site_content?: SiteContentExtraction;
  color_theme?: ColorThemeExtraction;
  template_data?: TemplateGenerationData;

  // Cost tracking
  cost: AuditCost;

  // Data quality / scrape info (server-generated, not from the model)
  scrape_summary?: ScrapeSummary;
}

// Website content scraped from URL
export interface WebsiteContent {
  url: string;
  title: string;
  description: string;
  headings: string[];
  text: string;
  images: number;
  structuredProducts?: Array<{ name: string; price?: string; description?: string }>;
  links: {
    internal: number;
    external: number;
  };
  meta: {
    keywords?: string;
    author?: string;
    viewport?: string;
    robots?: string;
  };
  hasSSL: boolean;
  responseTime: number;
  wordCount: number;
  textPreview: string;
  sampledUrls?: string[];
}

// API request body
export interface AuditRequest {
  url: string;
  auditMode?: AuditMode;
}
