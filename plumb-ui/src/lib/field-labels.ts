// Human-readable labels for snake_case field names from extraction

const FIELD_LABELS: Record<string, string> = {
  // Construction loan fields
  total_development_cost: "Total Development Cost",
  land_cost: "Land Cost",
  hard_costs: "Hard Costs",
  soft_costs: "Soft Costs",
  financing_costs: "Financing Costs",
  equity_contribution: "Equity Contribution",
  loan_amount_requested: "Loan Amount Requested",
  ltc_requested: "LTC (Requested)",
  ltc_calculated: "LTC (Calculated)",
  completion_date: "Completion Date",
  projected_sellout: "Projected Sellout",
  projected_sellout_per_sf: "Projected Sellout / SF",
  profit_margin_on_cost: "Profit Margin on Cost",

  // Property fields
  property_address: "Property Address",
  property_type: "Property Type",
  total_units: "Total Units",
  total_gsf: "Gross Square Footage",
  lot_area: "Lot Area",
  floors: "Floors",
  year_built: "Year Built",

  // Sponsor fields
  sponsor_name: "Sponsor Name",
  sponsor_entity: "Sponsor Entity",
  completed_projects: "Completed Projects",
  total_dev_value: "Total Development Value",

  // Regulatory fields
  zoning: "Zoning",
  far: "FAR",
  permits: "Permits",
  approval_status: "Approval Status",

  // Stabilized debt fields
  gross_potential_rent: "Gross Potential Rent",
  vacancy_rate: "Vacancy Rate",
  effective_gross_income: "Effective Gross Income",
  noi: "NOI",
  dscr: "DSCR",
  ltv: "LTV",
  cap_rate: "Cap Rate",
  debt_yield: "Debt Yield",
  loan_amount: "Loan Amount",
  interest_rate_assumption: "Interest Rate",
  amortization: "Amortization",
  loan_term: "Loan Term",
};

export function fieldLabel(fieldName: string): string {
  return FIELD_LABELS[fieldName] || fieldName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
