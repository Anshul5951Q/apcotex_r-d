import type { PatentRecipeStep } from "./recipeSimulatorPatentData";

export interface SpecRowTemplate {
  feature: string;
  unit: string;
  category?: string;
  dataType?: 'number' | 'text' | 'boolean';
  id: string;
}

export const SPEC_ROWS: SpecRowTemplate[] = [
  { id: "prop-1", feature: "BACN", unit: "%", category: "General", dataType: "number" },
  { id: "prop-2", feature: "Mooney (ML1+4 @ 100°C)", unit: "MU", category: "General", dataType: "number" },
  { id: "prop-3", feature: "Stress Relaxation", unit: "sec", category: "General", dataType: "number" },
  { id: "prop-4", feature: "pH", unit: "—", category: "General", dataType: "number" },
  { id: "prop-5", feature: "Total Solid Content", unit: "%", category: "General", dataType: "number" },
  { id: "prop-6", feature: "Gel Content", unit: "%", category: "General", dataType: "number" },
  { id: "prop-7", feature: "Tg", unit: "°C", category: "Thermal", dataType: "number" },
  { id: "prop-8", feature: "Volatile Matter", unit: "%", category: "General", dataType: "number" },
  { id: "prop-9", feature: "Particle Size", unit: "nm", category: "Physical", dataType: "number" },
  { id: "prop-10", feature: "Carboxylation", unit: "%", category: "General", dataType: "number" },
  { id: "prop-11", feature: "Density", unit: "g/ml", category: "Physical", dataType: "number" },
  { id: "prop-12", feature: "Thermal Colloidal Stability", unit: "%", category: "Stability", dataType: "number" },
  { id: "prop-13", feature: "Mechanical Colloidal Stability", unit: "%", category: "Stability", dataType: "number" },
  { id: "prop-14", feature: "Chemical Colloidal Stability", unit: "%", category: "Stability", dataType: "number" },
  { id: "prop-15", feature: "Number-average Molecular Weight (Mn)", unit: "g/mol", category: "Molecular", dataType: "number" },
  { id: "prop-16", feature: "Weight-average Molecular Weight (Mw)", unit: "g/mol", category: "Molecular", dataType: "number" },
  { id: "prop-17", feature: "Z-average Molecular Weight (Mz)", unit: "g/mol", category: "Molecular", dataType: "number" },
  { id: "prop-18", feature: "Z+1-average Molecular Weight (Mz+1)", unit: "g/mol", category: "Molecular", dataType: "number" },
  { id: "prop-19", feature: "Polydispersity Index (PDI)", unit: "—", category: "Molecular", dataType: "number" },
];

export interface RecipeProperty {
  id: string;
  name: string;
  value: string;
  unit: string;
  source?: string;
  patentRef?: string;
}

export interface EditableRecipe {
  id: string;
  name: string;
  rank: number;
  confidence: number;
  patentSupport: string;
  topPick?: boolean;
  properties: RecipeProperty[];
  // Include raw data for passing to steps
  raw_data?: any; 
}

// Convert from API LLM structure to EditableRecipe structure
export function convertToEditableRecipe(recipe: any): EditableRecipe {
  const params = recipe.recipe_data?.parameters || [];
  const props: RecipeProperty[] = params.map((p: any, i: number) => ({
    id: `prop-${i}`,
    name: p.name,
    value: p.value,
    unit: p.unit,
    source: p.source,
    patentRef: p.patent_ref
  }));

  // Ensure some base properties exist even if LLM omits them
  if (props.length === 0) {
    props.push({ id: "bdAcnRatio", name: "BD/ACN Ratio", value: recipe.recipe_data?.bd_acn_ratio || "", unit: "" });
    props.push({ id: "method", name: "Method", value: recipe.recipe_data?.polymerization_method || "", unit: "" });
    props.push({ id: "temperature", name: "Temperature", value: recipe.recipe_data?.temperature || "", unit: "" });
    props.push({ id: "conversion", name: "Conversion", value: recipe.recipe_data?.conversion || "", unit: "" });
  }

  return {
    id: recipe.id,
    name: recipe.name,
    rank: recipe.rank,
    confidence: recipe.evidence_coverage_score, // Using evidence score instead of fake confidence
    patentSupport: (recipe.patent_references || []).join(", "),
    topPick: recipe.rank === 1,
    properties: props,
    raw_data: recipe.recipe_data
  };
}

export function getPolymerizationRecipeSteps(
  recipeData: any,
): PatentRecipeStep[] {
  // If no raw data is available, return empty or generic steps
  if (!recipeData) return [];
  
  return [
    {
      param: "Monomer Charge",
      step: "PR#1",
      desc: `Charge butadiene/acrylonitrile at ${recipeData.bd_acn_ratio || "target"} ratio per ${recipeData.polymerization_method || "standard"} protocol`,
      temp: "25°C",
      duration: "15 min",
    },
    {
      param: "Water Addition",
      step: "PR#2",
      desc: `Add deionized water at ${recipeData.water || "target"} with high-shear dispersion`,
      temp: "25°C",
      duration: "12 min",
    },
    {
      param: "Emulsifier",
      step: "PR#3",
      desc: `Add ${recipeData.emulsifier || "target"} and stabilize emulsion before polymerization`,
      temp: "25°C",
      duration: "10 min",
    },
    {
      param: "Temperature Ramp",
      step: "PR#4",
      desc: `Ramp reactor to ${recipeData.temperature || "target"} for controlled kinetics`,
      temp: recipeData.temperature || "target",
      duration: "20 min",
    },
    {
      param: "Initiator",
      step: "PR#5",
      desc: `Dose ${recipeData.initiator || "target"} to initiate emulsion polymerization`,
      temp: recipeData.temperature || "target",
      duration: "5 min",
    },
    {
      param: "Chain Transfer Agent",
      step: "PR#6",
      desc: `Add ${recipeData.chain_transfer_agent || "target"} for molecular weight control`,
      temp: recipeData.temperature || "target",
      duration: "8 min",
    },
    {
      param: "Polymerization Hold",
      step: "PR#7",
      desc: `Maintain reaction until ${recipeData.conversion || "target"} conversion is achieved`,
      temp: recipeData.temperature || "target",
      duration: "420 min",
    },
    {
      param: "Coagulation",
      step: "PR#8",
      desc: `Coagulate latex using ${recipeData.coagulant || "target"} under standard plant conditions`,
      temp: "65°C",
      duration: "45 min",
    },
    {
      param: "Washing & Drying",
      step: "PR#9",
      desc: "Wash crumbs, dry, and sample for BACN and Mooney verification",
      temp: "100°C",
      duration: "90 min",
    },
    {
      param: "Quality Release",
      step: "PR#10",
      desc: `Target release at BACN ${recipeData.expected_bound_acn || "target"} and Mooney ${recipeData.expected_mooney || "target"}`,
      temp: "25°C",
      duration: "20 min",
    },
  ];
}

export interface CustomerFeedbackOption {
  id: string;
  label: string;
  checked: boolean;
}

export const CUSTOMER_FEEDBACK_PROPERTIES: SpecRowTemplate[] = [
  { id: "cf-prop-1", feature: "MH", unit: "lb-in", category: "Testing", dataType: "number" },
  { id: "cf-prop-2", feature: "Ts1", unit: "min", category: "Testing", dataType: "number" },
  { id: "cf-prop-3", feature: "Ts2", unit: "min", category: "Testing", dataType: "number" },
  { id: "cf-prop-4", feature: "T10", unit: "min", category: "Testing", dataType: "number" },
  { id: "cf-prop-5", feature: "T50", unit: "min", category: "Testing", dataType: "number" },
  { id: "cf-prop-6", feature: "T90", unit: "min", category: "Testing", dataType: "number" },
  { id: "cf-prop-7", feature: "Hardness", unit: "Shore A", category: "Testing", dataType: "number" },
  { id: "cf-prop-8", feature: "Tensile Strength", unit: "MPa", category: "Testing", dataType: "number" },
  { id: "cf-prop-9", feature: "Elongation at Break", unit: "%", category: "Testing", dataType: "number" },
  { id: "cf-prop-10", feature: "Modulus at 100%", unit: "MPa", category: "Testing", dataType: "number" },
  { id: "cf-prop-11", feature: "Modulus at 300%", unit: "MPa", category: "Testing", dataType: "number" },
  { id: "cf-prop-12", feature: "Tear Strength", unit: "N/mm", category: "Testing", dataType: "number" },
  { id: "cf-prop-13", feature: "Compression Set", unit: "%", category: "Testing", dataType: "number" },
  { id: "cf-prop-14", feature: "Abrasion Resistance", unit: "mm³", category: "Testing", dataType: "number" },
  { id: "cf-prop-15", feature: "Volume Swell (IRM 903)", unit: "%", category: "Testing", dataType: "number" },
  { id: "cf-prop-16", feature: "Weight Change (Isooctane)", unit: "%", category: "Testing", dataType: "number" },
  { id: "cf-prop-17", feature: "Change in Hardness (Aged)", unit: "Points", category: "Testing", dataType: "number" },
  { id: "cf-prop-18", feature: "Change in Tensile Strength", unit: "%", category: "Testing", dataType: "number" },
  { id: "cf-prop-19", feature: "Change in Elongation", unit: "%", category: "Testing", dataType: "number" },
  { id: "cf-prop-20", feature: "Processing Oil", unit: "phr", category: "Formulation", dataType: "number" },
];

// Re-export type definitions for usage
export interface OptimizedRecipe {
  id: string;
  revision: string;
  name: string;
  description: string;
  changes: Array<{
    parameter: string;
    previous: string;
    revised: string;
    rationale: string;
  }>;
  impacts: Array<{
    property: string;
    expectedChange: string;
    description: string;
  }>;
  properties: RecipeProperty[];
  raw_data?: any;
}

export interface MeasuredValueRow {
  property: string;
  target: string;
  actual: string;
}

export type TransferredSpecData = {
  property: string;
  unit: string;
  min: string;
  max: string;
  competitors: Record<string, string>; // name -> value
};
