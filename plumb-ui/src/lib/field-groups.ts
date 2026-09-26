// Field → category mapping for triage queue sorting order

export type FieldGroup = "financial" | "property" | "sponsor" | "regulatory" | "other";

const FIELD_GROUP_MAP: Record<string, FieldGroup> = {
  total_development_cost: "financial",
  land_cost: "financial",
  hard_costs: "financial",
  soft_costs: "financial",
  financing_costs: "financial",
  equity_contribution: "financial",
  loan_amount_requested: "financial",
  ltc_requested: "financial",
  ltc_calculated: "financial",
  projected_sellout: "financial",
  projected_sellout_per_sf: "financial",
  profit_margin_on_cost: "financial",
  gross_potential_rent: "financial",
  vacancy_rate: "financial",
  effective_gross_income: "financial",
  noi: "financial",
  dscr: "financial",
  ltv: "financial",
  cap_rate: "financial",
  debt_yield: "financial",
  loan_amount: "financial",
  interest_rate_assumption: "financial",
  amortization: "financial",
  loan_term: "financial",

  property_address: "property",
  property_type: "property",
  total_units: "property",
  total_gsf: "property",
  lot_area: "property",
  floors: "property",
  year_built: "property",
  completion_date: "property",

  sponsor_name: "sponsor",
  sponsor_entity: "sponsor",
  completed_projects: "sponsor",
  total_dev_value: "sponsor",

  zoning: "regulatory",
  far: "regulatory",
  permits: "regulatory",
  approval_status: "regulatory",
};

const GROUP_ORDER: Record<FieldGroup, number> = {
  financial: 0,
  property: 1,
  sponsor: 2,
  regulatory: 3,
  other: 4,
};

export function fieldGroup(fieldName: string): FieldGroup {
  return FIELD_GROUP_MAP[fieldName] || "other";
}

export function fieldGroupOrder(fieldName: string): number {
  return GROUP_ORDER[fieldGroup(fieldName)];
}
