// Types mirroring backend Pydantic schemas

// --- Enums ---

export type DealType = "construction_loan" | "stabilized_debt" | "value_add" | "equity_placement";

export type DealSubtype =
  | "ground_up_residential"
  | "ground_up_commercial"
  | "multifamily_rental"
  | "condo_sellout"
  | "mixed_use"
  | "office"
  | "industrial"
  | "retail";

export type CapitalAsk = "debt" | "equity" | "mezz" | "preferred_equity";

export type PropertyType =
  | "multifamily_rental"
  | "condo_sellout"
  | "office"
  | "industrial"
  | "retail"
  | "mixed_use";

export type DealStatus =
  | "docs_received"
  | "classifying"
  | "extracting"
  | "extraction_review"
  | "model_building"
  | "market_enrichment"
  | "om_drafting"
  | "om_review"
  | "reworking"
  | "lender_outreach"
  | "tracking"
  | "term_sheet_received"
  | "closed"
  | "on_hold"
  | "dead"
  | "extraction_failed"
  | "model_error";

export type DocumentType =
  | "project_summary_deck"
  | "pro_forma"
  | "rent_roll"
  | "operating_statement_t12"
  | "appraisal"
  | "environmental_report"
  | "property_condition_report"
  | "zoning_approval"
  | "permit"
  | "sponsor_resume"
  | "legal_document"
  | "market_research_report"
  | "comp_report"
  | "submarket_overview"
  | "costar_export"
  | "argus_dcf"
  | "other";

export type DocumentStatus =
  | "uploaded"
  | "parsing"
  | "parsed"
  | "extracting"
  | "extracted"
  | "failed"
  | "superseded";

export type FlagColor = "green" | "yellow" | "red";

export type ExtractionMethod = "docling" | "claude_vision" | "openpyxl" | "manual";

export type CrossRefResult = "match" | "mismatch" | "within_tolerance" | "unable_to_check";

export type CrossRefResolution = "field_a_correct" | "field_b_correct" | "both_wrong";

export type EventType =
  | "doc_uploaded"
  | "doc_classified"
  | "doc_parsed"
  | "doc_superseded"
  | "extraction_started"
  | "extraction_completed"
  | "extraction_failed"
  | "field_reviewed"
  | "field_overridden"
  | "cross_ref_resolved"
  | "checkpoint_released"
  | "model_calculated"
  | "model_failed"
  | "public_data_fetched"
  | "market_data_imported"
  | "om_generated"
  | "om_approved"
  | "lender_contacted"
  | "response_received"
  | "term_sheet_received"
  | "llm_call"
  | "deal_created"
  | "deal_updated"
  | "state_transition"
  | "backward_transition"
  | "revision_started"
  | "deal_on_hold"
  | "deal_resumed"
  | "deal_killed";

export type UserRole = "admin" | "analyst" | "broker";

export type DeadReason =
  | "borrower_unresponsive"
  | "numbers_dont_work"
  | "lender_passed_all"
  | "duplicate"
  | "out_of_scope"
  | "other";

// --- Response types ---

export interface Deal {
  id: string;
  deal_type: DealType;
  deal_subtype: DealSubtype | null;
  capital_ask: CapitalAsk | null;
  status: DealStatus;
  revision_number: number;
  property_name: string | null;
  property_address: string | null;
  property_type: PropertyType | null;
  sponsor: Record<string, unknown> | null;
  regulatory: Record<string, unknown> | null;
  typed_extension: Record<string, unknown> | null;
  market_context: MarketContext | null;
  created_at: string;
  updated_at: string;
  version: number;
  created_by: string;
}

export interface DealListResponse {
  deals: Deal[];
  total: number;
}

export interface Document {
  id: string;
  deal_id: string;
  filename: string;
  document_type: DocumentType | null;
  mime_type: string;
  s3_key: string;
  file_size: number | null;
  page_count: number | null;
  classification_confidence: number | null;
  status: DocumentStatus;
  superseded_by: string | null;
  uploaded_at: string;
  uploaded_by: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export interface ConfidenceBasis {
  source_type: "table_cell" | "list_item" | "paragraph" | "footnote" | "inferred";
  label_match: "exact" | "synonym" | "contextual";
  corroborated: boolean;
  ocr_sourced: boolean;
  adjustments_applied: string[] | null;
}

export interface ExtractedValue {
  id: string;
  deal_id: string;
  field_name: string;
  value: string | null;
  source_doc_id: string | null;
  source_page: number | null;
  source_text_snippet: string | null;
  confidence_score: number | null;
  confidence_basis: ConfidenceBasis | null;
  extraction_method: ExtractionMethod | null;
  prompt_version: string | null;
  flag: FlagColor;
  reviewed_by: string | null;
  reviewed_at: string | null;
  override_value: string | null;
  override_reason: string | null;
  version: number;
  created_at: string;
}

export interface ExtractedValueListResponse {
  values: ExtractedValue[];
  total: number;
}

export interface CrossReference {
  id: string;
  deal_id: string;
  rule_name: string;
  field_a: string;
  field_a_value: string | null;
  field_a_source_doc_id: string | null;
  field_b: string;
  field_b_value: string | null;
  field_b_source_doc_id: string | null;
  result: CrossRefResult;
  tolerance_applied: string | null;
  delta: string | null;
  resolution: CrossRefResolution | null;
  resolved_by: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface CrossReferenceListResponse {
  cross_references: CrossReference[];
  total: number;
}

export interface Event {
  id: string;
  deal_id: string;
  event_type: EventType;
  actor_id: string | null;
  payload: Record<string, unknown> | null;
  revision_number: number;
  timestamp: string;
}

export interface EventListResponse {
  events: Event[];
  total: number;
}

export interface ExtractionStatus {
  deal_id: string;
  deal_status: string;
  documents: DocumentExtractionStatus[];
  total_fields_extracted: number;
  fields_by_flag: Record<string, number>;
}

export interface DocumentExtractionStatus {
  doc_id: string;
  filename: string;
  document_type: string | null;
  status: string;
  classification_confidence: number | null;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

// --- Market Intelligence types ---

export interface MarketDataRecord {
  id: string;
  deal_id: string;
  data_source: string;
  data_type: string;
  data: Record<string, unknown> | null;
  source_url: string | null;
  confidence_score: number | null;
}

export interface MarketDataListResponse {
  records: MarketDataRecord[];
  total: number;
}

export interface FetcherStatus {
  data_source: string;
  data_type?: string;
  status: string;
  confidence?: number | null;
  source_url?: string | null;
}

export interface MarketStatus {
  deal_id: string;
  deal_status: string;
  fetchers: Record<string, FetcherStatus>;
  total_records: number;
  has_market_context: boolean;
}

export interface MarketContext {
  property_history: Record<string, unknown> | null;
  zoning: Record<string, unknown> | null;
  permits: Record<string, unknown> | null;
  news: unknown[];
  offering_plan: Record<string, unknown> | null;
  comps: unknown[];
  market_stats: Record<string, unknown> | null;
  dcf: Record<string, unknown> | null;
  sponsor_portfolio: Record<string, unknown> | null;
  validation_flags: ValidationFlag[];
  overall_assessment: string | null;
  validation_summary: string | null;
  data_sources_used: Record<string, unknown>[];
  assembled_at: string;
}

export interface ValidationFlag {
  field: string;
  borrower_value?: string | null;
  market_value?: string | null;
  severity: "info" | "warning" | "critical";
  explanation: string;
}

export interface ImportResponse {
  status: string;
  importer: string | null;
  records_imported: number;
  warnings: string[];
}

// --- Request types ---

export interface DealCreateRequest {
  deal_type: DealType;
  deal_subtype?: DealSubtype;
  capital_ask?: CapitalAsk;
  property_name?: string;
  property_address?: string;
  property_type?: PropertyType;
  typed_extension?: Record<string, unknown>;
}

export interface TransitionRequest {
  target_status: DealStatus;
  reason?: string;
  dead_reason?: DeadReason;
}

export interface OverrideRequest {
  override_value: string;
  override_reason: string;
  version: number;
}

export interface ResolveRequest {
  resolution: CrossRefResolution;
}

// --- Financial Model types ---

export interface ModelAssumptions {
  cap_rate: number;
  vacancy_fm: number;
  vacancy_affordable: number;
  vacancy_retail: number;
  mgmt_fee_pct: number;
  assessment_growth: number;
  tax_rate_growth: number;
  discount_rate: number;
}

export interface SourcesUsesLine {
  label: string;
  total: number;
  pct_total: number;
  per_zfa: number | null;
  per_gsf: number | null;
  per_nra: number | null;
  prior_to_closing: number;
  at_closing: number;
  future_funding: number;
}

export interface SourcesUses {
  sources: SourcesUsesLine[];
  uses: SourcesUsesLine[];
  total_sources: SourcesUsesLine;
  total_uses: SourcesUsesLine;
}

export interface BudgetLineItem {
  category: string;
  label: string;
  total_cost: number;
  pct_total: number;
  per_zfa: number | null;
  per_gsf: number | null;
  per_nsf: number | null;
  spent_to_date: number;
  at_closing: number;
  future_funding: number;
  rate_pct: number | null;
}

export interface UnitMixRow {
  tier: string;
  beds: number | null;
  baths: number | null;
  units: number;
  sf_per_unit: number;
  avg_monthly_rent: number;
  rent_per_sf: number;
}

export interface UnitMixTiered {
  fm: UnitMixRow[];
  affordable_421a: UnitMixRow[];
  mih: UnitMixRow[];
  commercial: UnitMixRow[];
  total: UnitMixRow[];
}

export interface ProFormaLine {
  label: string;
  per_sf: number | null;
  per_unit_yr: number | null;
  pct_of_egi: number | null;
  total: number;
  is_subtotal: boolean;
}

export interface RentalProForma {
  income_lines: ProFormaLine[];
  egi: ProFormaLine;
  expense_lines: ProFormaLine[];
  total_expenses: ProFormaLine;
  noi: ProFormaLine;
}

export interface ValuationSummary {
  actual_noi: number;
  yield_on_cost: number;
  full_tax_noi: number;
  cap_rate: number;
  estimated_value_a: number;
  abatement_value_b: number;
  total_asset_value: number;
  value_per_unit: number;
  value_per_gsf: number;
  total_project_cap: number;
  construction_loan: number;
  stabilized_ltv: number;
  debt_yield: number;
  debt_per_unit: number;
  debt_per_gsf: number;
}

export interface AbatementYear {
  year: number;
  benefit_year_start: string;
  taxable_assessment: number;
  av_prior: number;
  increase_in_av: number;
  pct_exempt: number;
  exemption_amount: number;
  final_taxable_assessment: number;
  tax_rate: number;
  unabated_ret: number;
  abated_ret: number;
  ret_savings: number;
}

export interface AbatementSchedule {
  program_option: string;
  borough: string;
  block_lot: string;
  av_prior_to_construction: number;
  assessment_growth_rate: number;
  tax_rate_growth: number;
  discount_rate: number;
  npv_of_tax_savings: number;
  years: AbatementYear[];
}

export interface SensitivityCell {
  asset_value: number;
  ltv: number;
  debt_yield: number;
}

export interface SensitivityMatrix {
  cap_rates: number[];
  rent_growth_rates: number[];
  cells: SensitivityCell[][];
  base_row: number;
  base_col: number;
}

export interface CalculatedValue {
  result: unknown;
  formula: string;
  inputs: Record<string, unknown>;
}

export interface FinancialModel {
  deal_id: string;
  assumptions: ModelAssumptions;
  sources_uses: SourcesUses;
  budget_detail: BudgetLineItem[];
  unit_mix: UnitMixTiered;
  proforma: RentalProForma;
  valuation: ValuationSummary;
  abatement: AbatementSchedule | null;
  sensitivity: SensitivityMatrix;
  ltc: number;
  total_development_cost: number;
  loan_amount: number;
  equity: number;
  total_units: number;
  total_gsf: number;
  zfa: number | null;
  nra: number;
  provenance: Record<string, CalculatedValue>;
  calculated_at: string;
  errors: string[];
}

export interface CalculateResponse {
  deal_id: string;
  status: "success" | "error";
  model: FinancialModel | null;
  errors: string[];
}

export interface AssumptionsUpdate {
  cap_rate?: number;
  vacancy_fm?: number;
  vacancy_affordable?: number;
  vacancy_retail?: number;
  mgmt_fee_pct?: number;
  assessment_growth?: number;
  tax_rate_growth?: number;
  discount_rate?: number;
}

// --- OM types ---

export interface OMVersion {
  id: string;
  deal_id: string;
  version_number: number;
  page_count: number | null;
  file_size: number | null;
  generated_at: string | null;
  status: string;
}

export interface OMVersionListResponse {
  versions: OMVersion[];
}

export interface OMStatusResponse {
  deal_id: string;
  status: "idle" | "generating" | "ready";
  latest_version: OMVersion | null;
}

export interface OMGenerateResponse {
  deal_id: string;
  status: string;
  message: string;
}

export interface OMNarrativeUpdate {
  transaction_overview?: string[] | null;
  investment_highlights?: Record<string, string>[] | null;
  market_narrative?: Record<string, string>[] | null;
  sponsor_bios?: Record<string, string[]> | null;
}

// --- Expert feedback / redlines ---

export type RedlineCategory =
  | "factual_error"
  | "tone"
  | "omission"
  | "aggressive_assumption"
  | "compliance"
  | "positioning";

export type RedlineSeverity = "minor" | "moderate" | "material";

export interface Redline {
  id: string;
  deal_id: string;
  artifact_type: string;
  artifact_ref_id: string;
  section_key: string;
  section_index: number | null;
  original_text: string;
  edited_text: string;
  rationale: string | null;
  correction_category: RedlineCategory | null;
  severity: RedlineSeverity;
  archetype_signature: string | null;
  reviewer_id: string | null;
  reviewer_role: string | null;
  episode_id: string | null;
  applied_in_version_id: string | null;
  created_at: string;
}

export interface RedlineListResponse {
  redlines: Redline[];
  total: number;
}

export interface RedlineCreate {
  artifact_type?: string;
  section_key: string;
  section_index?: number | null;
  original_text: string;
  edited_text: string;
  rationale?: string | null;
  correction_category?: RedlineCategory | null;
  severity?: RedlineSeverity;
}

export interface RerunWithFeedbackResponse {
  deal_id: string;
  status: string;
  message: string;
  lessons_applied: string[];
}

export interface OMNarrativeSnapshot {
  version_id: string;
  version_number: number;
  transaction_overview: string[];
  investment_highlights: Array<{ header?: string; body?: string }>;
  market_narrative: Array<{ header?: string; body?: string }>;
  sponsor_bios: Record<string, string[]>;
  redline_count: number;
  archetype_signature: string | null;
  approval_status: string | null;
}

export interface OMApproveResponse {
  deal_id: string;
  version_id: string;
  status: string;
  archetype_signature: string | null;
  exemplar_eligible: boolean;
}

// --- Sprint 1: Metrics ---

export interface StageDuration {
  stage_name: string;
  entered_at: string | null;
  exited_at: string | null;
  duration_seconds: number | null;
  revision_number: number;
}

export interface DealVelocity {
  deal_id: string;
  stages: StageDuration[];
  total_turnaround_seconds: number;
  human_wait_seconds: number;
}

export interface AggregateVelocity {
  stages: {
    stage_name: string;
    avg_duration_seconds: number;
    min_duration_seconds: number | null;
    max_duration_seconds: number | null;
    count: number;
  }[];
}

export interface AggregateQuality {
  total_fields: number;
  overridden_fields: number;
  override_rate: number;
}

export interface FieldAccuracy {
  fields: {
    field_name: string;
    total: number;
    overridden: number;
    override_rate: number;
  }[];
}

export interface AggregateCost {
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
  total_calls: number;
}

export interface DealCost {
  deal_id: string;
  total_cost_usd: number;
  by_prompt: {
    prompt_name: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    calls: number;
  }[];
}

export interface Alert {
  id: string;
  deal_id: string;
  alert_type: string;
  stage_name: string | null;
  message: string;
  severity: string;
  created_at: string | null;
}

export interface Bottleneck {
  stage_name: string;
  waiting_count: number;
}

// --- Sprint 2: Skills ---

export interface Skill {
  id: string;
  name: string;
  description: string | null;
  skill_type: string;
  target_prompt: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
  versions?: SkillVersionSummary[];
}

export interface SkillVersionSummary {
  id: string;
  version_number: number;
  is_active: boolean;
  regression_passed: boolean | null;
  overall_accuracy: number | null;
  created_at: string | null;
  published_at: string | null;
}

export interface SkillVersion {
  id: string;
  version_number: number;
  instructions: string;
  reference_examples: unknown[];
  is_active: boolean;
  regression_passed: boolean | null;
  created_at: string | null;
}

export interface SkillTestResult {
  id: string;
  skill_version_id: string;
  deal_id: string;
  results: Record<string, unknown> | null;
  overall_accuracy: number | null;
  improvement_delta: number | null;
  tested_at: string | null;
}

export interface KnowledgeEntry {
  id: string;
  entry_type: string;
  title: string;
  content: string;
  tags: string[];
  created_at: string | null;
  updated_at: string | null;
}

// --- Sprint 3: Lenders + Developers ---

export interface Lender {
  id: string;
  name: string;
  lender_type: string;
  general_preferences: Record<string, unknown> | null;
  credit_committee_notes: string | null;
  relationship_contacts: unknown[];
  notes: string | null;
  current_appetite: LenderAppetiteSummary | null;
  appetite_history?: LenderAppetiteRecord[];
  transactions?: LenderTransactionRecord[];
}

export interface LenderSummary {
  id: string;
  name: string;
  lender_type: string;
  notes: string | null;
  created_at: string | null;
}

export interface LenderAppetiteSummary {
  appetite_signal: string;
  property_types: string[];
  geographies: string[];
  deal_size_min: number | null;
  deal_size_max: number | null;
  ltc_max: number | null;
  rate_indication: string | null;
  is_stale: boolean;
  recorded_at: string | null;
}

export interface LenderAppetiteRecord {
  appetite_signal: string;
  source_detail: string | null;
  recorded_at: string | null;
  is_stale: boolean;
}

export interface LenderTransactionRecord {
  id: string;
  property_type: string | null;
  geography: string | null;
  deal_size: number | null;
  outcome: string | null;
  recorded_at: string | null;
}

export interface LenderMatch {
  lender_id: string;
  lender_name: string;
  lender_type: string;
  fit_score: number;
  appetite_signal: string;
  rate_indication: string | null;
  ltc_max: number | null;
  notes: string | null;
}

export interface Developer {
  id: string;
  name: string;
  entity_structure: Record<string, unknown> | null;
  track_record: string | null;
  known_patterns: unknown[];
  notes: string | null;
  deal_count: number;
  deals?: { deal_id: string; role: string }[];
  correction_patterns?: { field_name: string; override_count: number }[];
}

export interface DeveloperSummary {
  id: string;
  name: string;
  deal_count: number;
  notes: string | null;
  created_at: string | null;
}

export interface Episode {
  id: string;
  deal_id: string | null;
  event_type: string;
  lesson: string;
  relevance_tags: string[];
  confidence: string;
  occurrence_count: number;
  created_at: string | null;
}

// --- Sprint 4: Agent ---

export interface FeatureFlag {
  id: string;
  flag_name: string;
  enabled: boolean;
  enabled_deal_types: string[];
  enabled_deal_ids: string[];
}

export interface AgentRun {
  id: string;
  deal_id: string;
  agent_name: string;
  goal?: string;
  status: string;
  iterations: number;
  reasoning_trace?: Record<string, unknown>[];
  result?: Record<string, unknown>;
  error: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface AgentTool {
  name: string;
  description: string;
  permission: string;
}
