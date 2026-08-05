import type { PatentRecipeStep } from "./recipeSimulatorPatentData";

export interface SpecRowTemplate {
  feature: string;
  unit: string;
  basf: string;
  syn: string;
  tri: string;
  category?: string;
  dataType?: 'number' | 'text' | 'boolean';
  id: string;
}

export const SPEC_ROWS: SpecRowTemplate[] = [
  {
    id: "prop-1",
    feature: "BACN",
    unit: "%",
    basf: "24.5",
    syn: "22.1",
    tri: "26.3",
    category: "General",
    dataType: "number",
  },
  {
    id: "prop-2",
    feature: "Mooney (ML1+4 @ 100°C)",
    unit: "MU",
    basf: "48",
    syn: "45",
    tri: "52",
    category: "General",
    dataType: "number",
  },
  {
    id: "prop-3",
    feature: "Stress Relaxation",
    unit: "sec",
    basf: "14",
    syn: "12",
    tri: "16",
    category: "General",
    dataType: "number",
  },
  {
    id: "prop-4",
    feature: "pH",
    unit: "—",
    basf: "7.2",
    syn: "7.5",
    tri: "7.0",
    category: "General",
    dataType: "number",
  },
  {
    id: "prop-5",
    feature: "Total Solid Content",
    unit: "%",
    basf: "48.5",
    syn: "50.2",
    tri: "46.8",
    category: "General",
    dataType: "number",
  },
  {
    id: "prop-6",
    feature: "Gel Content",
    unit: "%",
    basf: "1.8",
    syn: "2.0",
    tri: "1.5",
    category: "General",
    dataType: "number",
  },
  {
    id: "prop-7",
    feature: "Tg",
    unit: "°C",
    basf: "-18",
    syn: "-21",
    tri: "-15",
    category: "Thermal",
    dataType: "number",
  },
  {
    id: "prop-8",
    feature: "Volatile Matter",
    unit: "%",
    basf: "0.32",
    syn: "0.40",
    tri: "0.28",
    category: "General",
    dataType: "number",
  },
  {
    id: "prop-9",
    feature: "Particle Size",
    unit: "nm",
    basf: "120",
    syn: "135",
    tri: "115",
    category: "Physical",
    dataType: "number",
  },
  {
    id: "prop-10",
    feature: "Carboxylation",
    unit: "%",
    basf: "2.1",
    syn: "2.4",
    tri: "1.9",
    category: "General",
    dataType: "number",
  },
  {
    id: "prop-11",
    feature: "Density",
    unit: "g/ml",
    basf: "0.97",
    syn: "0.96",
    tri: "0.98",
    category: "Physical",
    dataType: "number",
  },
  {
    id: "prop-12",
    feature: "Thermal Colloidal Stability",
    unit: "%",
    basf: "95",
    syn: "93",
    tri: "96",
    category: "Stability",
    dataType: "number",
  },
  {
    id: "prop-13",
    feature: "Mechanical Colloidal Stability",
    unit: "%",
    basf: "94",
    syn: "92",
    tri: "95",
    category: "Stability",
    dataType: "number",
  },
  {
    id: "prop-14",
    feature: "Chemical Colloidal Stability",
    unit: "%",
    basf: "96",
    syn: "94",
    tri: "97",
    category: "Stability",
    dataType: "number",
  },
  {
    id: "prop-15",
    feature: "Number-average Molecular Weight (Mn)",
    unit: "g/mol",
    basf: "185000",
    syn: "178000",
    tri: "192000",
    category: "Molecular",
    dataType: "number",
  },
  {
    id: "prop-16",
    feature: "Weight-average Molecular Weight (Mw)",
    unit: "g/mol",
    basf: "420000",
    syn: "405000",
    tri: "438000",
    category: "Molecular",
    dataType: "number",
  },
  {
    id: "prop-17",
    feature: "Z-average Molecular Weight (Mz)",
    unit: "g/mol",
    basf: "780000",
    syn: "755000",
    tri: "810000",
    category: "Molecular",
    dataType: "number",
  },
  {
    id: "prop-18",
    feature: "Z+1-average Molecular Weight (Mz+1)",
    unit: "g/mol",
    basf: "980000",
    syn: "950000",
    tri: "1015000",
    category: "Molecular",
    dataType: "number",
  },
  {
    id: "prop-19",
    feature: "Polydispersity Index (PDI)",
    unit: "—",
    basf: "2.27",
    syn: "2.28",
    tri: "2.28",
    category: "Molecular",
    dataType: "number",
  },
];

export const DEMO_PATENT_VALUES: Record<
  string,
  Record<string, string>
> = {
  "BACN": { uspto: "24.8", espacenet: "27.0", inpass: "23.9" },
  "Mooney (ML1+4 @ 100°C)": { uspto: "46", espacenet: "50", inpass: "44" },
  "Stress Relaxation": { uspto: "13", espacenet: "15", inpass: "12" },
  pH: { uspto: "7.3", espacenet: "7.4", inpass: "7.2" },
  "Total Solid Content": { uspto: "49", espacenet: "50", inpass: "48" },
  "Gel Content": { uspto: "1.9", espacenet: "2.1", inpass: "1.7" },
  Tg: { uspto: "-17", espacenet: "-14", inpass: "-19" },
  "Volatile Matter": { uspto: "0.30", espacenet: "0.28", inpass: "0.35" },
  "Particle Size": { uspto: "125", espacenet: "130", inpass: "122" },
  "Carboxylation": { uspto: "2.0", espacenet: "2.3", inpass: "1.8" },
  "Density": { uspto: "0.96", espacenet: "0.98", inpass: "0.95" },
  "Thermal Colloidal Stability": { uspto: "94", espacenet: "96", inpass: "93" },
  "Mechanical Colloidal Stability": { uspto: "93", espacenet: "95", inpass: "92" },
  "Chemical Colloidal Stability": { uspto: "95", espacenet: "97", inpass: "94" },
  "Number-average Molecular Weight (Mn)": { uspto: "183000", espacenet: "188000", inpass: "180000" },
  "Weight-average Molecular Weight (Mw)": { uspto: "415000", espacenet: "428000", inpass: "402000" },
  "Z-average Molecular Weight (Mz)": { uspto: "770000", espacenet: "795000", inpass: "755000" },
  "Z+1-average Molecular Weight (Mz+1)": { uspto: "970000", espacenet: "1000000", inpass: "945000" },
  "Polydispersity Index (PDI)": { uspto: "2.27", espacenet: "2.28", inpass: "2.26" },
};

export interface PolymerizationRecipe {
  id: string;
  name: string;
  rank: number;
  confidence: number;
  patentSupport: string;
  topPick?: boolean;
  bdAcnRatio: string;
  method: string;
  temperature: string;
  water: string;
  emulsifier: string;
  initiator: string;
  chainTransferAgent: string;
  coagulant: string;
  conversion: string;
  expectedBoundAcn: string;
  expectedMooney: string;
}

export const POLYMERIZATION_RECIPES: PolymerizationRecipe[] = [
  {
    id: "recipe-1",
    name: "Recipe 1",
    rank: 1,
    confidence: 91,
    patentSupport: "US20250075019A1, EP3892656A1",
    topPick: true,
    bdAcnRatio: "72/28",
    method: "Cold Emulsion",
    temperature: "10°C",
    water: "180 phr",
    emulsifier: "Potassium Oleate",
    initiator: "Potassium Persulfate",
    chainTransferAgent: "tert-Dodecyl Mercaptan",
    coagulant: "Calcium Chloride",
    conversion: "92%",
    expectedBoundAcn: "24.8%",
    expectedMooney: "48",
  },
  {
    id: "recipe-2",
    name: "Recipe 2",
    rank: 2,
    confidence: 89,
    patentSupport: "EP3466997B1, US9932433B2",
    bdAcnRatio: "70/30",
    method: "Cold Emulsion",
    temperature: "10°C",
    water: "190 phr",
    emulsifier: "C30-C60 Dimer Acid / Potassium Oleate",
    initiator: "p-Menthane Hydroperoxide",
    chainTransferAgent: "tert-Dodecyl Mercaptan (0.45 phr)",
    coagulant: "Calcium Chloride",
    conversion: "88%",
    expectedBoundAcn: "24.5%",
    expectedMooney: "47",
  },
  {
    id: "recipe-3",
    name: "Recipe 3",
    rank: 3,
    confidence: 87,
    patentSupport: "US4435554A, US20160185890A1",
    bdAcnRatio: "67/33",
    method: "Warm Emulsion",
    temperature: "45°C",
    water: "200 phr",
    emulsifier: "Anionic Surfactant (Sulframin 1260)",
    initiator: "Potassium Persulfate",
    chainTransferAgent: "t-Dodecyl Mercaptan (0.55 phr)",
    coagulant: "Calcium Chloride + MH2PO4 Buffer",
    conversion: "85%",
    expectedBoundAcn: "25.2%",
    expectedMooney: "50",
  },
  {
    id: "recipe-4",
    name: "Recipe 4",
    rank: 4,
    confidence: 84,
    patentSupport: "US20140124986A1, EP3892656A1",
    bdAcnRatio: "74/26",
    method: "Cold Emulsion",
    temperature: "8°C",
    water: "185 phr",
    emulsifier: "Sulfosuccinate Ester / Fatty Acid Mixture",
    initiator: "Cumyl Hydroperoxide",
    chainTransferAgent: "C12-C16 Alkyl Thiol",
    coagulant: "Magnesium Sulfate",
    conversion: "90%",
    expectedBoundAcn: "24.2%",
    expectedMooney: "46",
  },
  {
    id: "recipe-5",
    name: "Recipe 5",
    rank: 5,
    confidence: 82,
    patentSupport: "US4255567A, US9932433B2",
    bdAcnRatio: "68/32",
    method: "Cold Emulsion (Divided ACN Feed)",
    temperature: "12°C",
    water: "195 phr",
    emulsifier: "Linear Alkyl Sulfate (C6-C10)",
    initiator: "Potassium Persulfate / Redox System",
    chainTransferAgent: "tert-Dodecyl Mercaptan (0.50 phr)",
    coagulant: "Colloidal Sulfur",
    conversion: "86%",
    expectedBoundAcn: "25.0%",
    expectedMooney: "49",
  },
];

export interface RecipeProperty {
  id: string;
  name: string;
  value: string;
  unit: string;
}

export interface EditableRecipe {
  id: string;
  name: string;
  rank: number;
  confidence: number;
  patentSupport: string;
  topPick?: boolean;
  properties: RecipeProperty[];
}

export function convertToEditableRecipe(recipe: PolymerizationRecipe): EditableRecipe {
  return {
    id: recipe.id,
    name: recipe.name,
    rank: recipe.rank,
    confidence: recipe.confidence,
    patentSupport: recipe.patentSupport,
    topPick: recipe.topPick,
    properties: [
      { id: "bdAcnRatio", name: "BD/ACN Ratio", value: recipe.bdAcnRatio, unit: "" },
      { id: "method", name: "Method", value: recipe.method, unit: "" },
      { id: "temperature", name: "Temperature", value: recipe.temperature, unit: "" },
      { id: "water", name: "Water", value: recipe.water, unit: "" },
      { id: "emulsifier", name: "Emulsifier", value: recipe.emulsifier, unit: "" },
      { id: "initiator", name: "Initiator", value: recipe.initiator, unit: "" },
      { id: "chainTransferAgent", name: "CTA", value: recipe.chainTransferAgent, unit: "" },
      { id: "coagulant", name: "Coagulant", value: recipe.coagulant, unit: "" },
      { id: "conversion", name: "Conversion", value: recipe.conversion, unit: "" },
      { id: "expectedBoundAcn", name: "Expected Bound ACN", value: recipe.expectedBoundAcn, unit: "" },
      { id: "expectedMooney", name: "Expected Mooney", value: recipe.expectedMooney, unit: "" },
    ],
  };
}

export function getPolymerizationRecipeSteps(
  recipe: PolymerizationRecipe,
): PatentRecipeStep[] {
  return [
    {
      param: "Monomer Charge",
      step: "PR#1",
      desc: `Charge butadiene/acrylonitrile at ${recipe.bdAcnRatio} ratio per ${recipe.method} protocol`,
      temp: "25°C",
      duration: "15 min",
    },
    {
      param: "Water Addition",
      step: "PR#2",
      desc: `Add deionized water at ${recipe.water} with high-shear dispersion`,
      temp: "25°C",
      duration: "12 min",
    },
    {
      param: "Emulsifier",
      step: "PR#3",
      desc: `Add ${recipe.emulsifier} and stabilize emulsion before polymerization`,
      temp: "25°C",
      duration: "10 min",
    },
    {
      param: "Temperature Ramp",
      step: "PR#4",
      desc: `Ramp reactor to ${recipe.temperature} for controlled cold-process kinetics`,
      temp: recipe.temperature,
      duration: "20 min",
    },
    {
      param: "Initiator",
      step: "PR#5",
      desc: `Dose ${recipe.initiator} to initiate emulsion polymerization`,
      temp: recipe.temperature,
      duration: "5 min",
    },
    {
      param: "Chain Transfer Agent",
      step: "PR#6",
      desc: `Add ${recipe.chainTransferAgent} for molecular weight and Mooney (ML1+4 @ 100°C) control`,
      temp: recipe.temperature,
      duration: "8 min",
    },
    {
      param: "Polymerization Hold",
      step: "PR#7",
      desc: `Maintain reaction until ${recipe.conversion} conversion is achieved`,
      temp: recipe.temperature,
      duration: "420 min",
    },
    {
      param: "Coagulation",
      step: "PR#8",
      desc: `Coagulate latex using ${recipe.coagulant} under standard plant conditions`,
      temp: "65°C",
      duration: "45 min",
    },
    {
      param: "Washing & Drying",
      step: "PR#9",
      desc: "Wash crumbs, dry, and sample for BACN and Mooney (ML1+4 @ 100°C) verification",
      temp: "100°C",
      duration: "90 min",
    },
    {
      param: "Quality Release",
      step: "PR#10",
      desc: `Target release at BACN ${recipe.expectedBoundAcn} and Mooney (ML1+4 @ 100°C) ${recipe.expectedMooney}`,
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

export const DEFAULT_CUSTOMER_FEEDBACK: CustomerFeedbackOption[] = [
  { id: "hardness", label: "Hardness Too Low", checked: true },
  { id: "oil", label: "Processing Oil Increased", checked: true },
  { id: "cure", label: "Cure Time Too Long", checked: false },
  { id: "compression", label: "Compression Set High", checked: false },
  { id: "processability", label: "Poor Processability", checked: false },
  { id: "tensile", label: "Low Tensile Strength", checked: false },
];

export interface MeasuredValueRow {
  property: string;
  target: string;
  actual: string;
}

export const DEMO_MEASURED_VALUES: MeasuredValueRow[] = [
  { property: "Hardness", target: "70", actual: "66" },
  { property: "Mooney (ML1+4 @ 100°C)", target: "50", actual: "47" },
  { property: "Processing Oil", target: "8 phr", actual: "12 phr" },
  { property: "Tensile Strength", target: "24 MPa", actual: "22 MPa" },
];

export const DEMO_CUSTOMER_NOTES =
  "Customer reports lower hardness than the competitor material. An additional 4 phr processing oil was required to achieve acceptable processing, increasing production cost. Customer requests equivalent performance with lower oil consumption while maintaining tensile strength.";

export const DEMO_TARGET_VALUES: Record<string, string> = {
  "BACN": "25",
  "Mooney (ML1+4 @ 100°C)": "48",
  "Stress Relaxation": "14",
  "pH": "7.2",
  "Total Solid Content": "48.5",
  "Gel Content": "1.8",
  "Tg": "-18",
  "Volatile Matter": "0.30",
  "Particle Size": "120",
  "Carboxylation": "2.1",
  "Density": "0.97",
  "Thermal Colloidal Stability": "95",
  "Mechanical Colloidal Stability": "94",
  "Chemical Colloidal Stability": "96",
  "Number-average Molecular Weight (Mn)": "185000",
  "Weight-average Molecular Weight (Mw)": "420000",
  "Z-average Molecular Weight (Mz)": "780000",
  "Z+1-average Molecular Weight (Mz+1)": "980000",
  "Polydispersity Index (PDI)": "2.27",
};

export const CUSTOMER_FEEDBACK_PROPERTIES: SpecRowTemplate[] = [
  {
    id: "cf-prop-1",
    feature: "MH",
    unit: "lb-in",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-2",
    feature: "Ts1",
    unit: "min",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-3",
    feature: "Ts2",
    unit: "min",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-4",
    feature: "T10",
    unit: "min",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-5",
    feature: "T50",
    unit: "min",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-6",
    feature: "T90",
    unit: "min",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-7",
    feature: "Hardness",
    unit: "Shore A",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-8",
    feature: "Tensile Strength",
    unit: "MPa",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-9",
    feature: "Elongation at Break",
    unit: "%",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-10",
    feature: "Modulus @ 100",
    unit: "MPa",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-11",
    feature: "Modulus @ 300",
    unit: "MPa",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-12",
    feature: "Tear Strength",
    unit: "lbf/in",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-13",
    feature: "Abrasion",
    unit: "mm³",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-14",
    feature: "Compression Set",
    unit: "%",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
  {
    id: "cf-prop-15",
    feature: "Ozone Resistance",
    unit: "—",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "text",
  },
  {
    id: "cf-prop-16",
    feature: "Rebound Resilience",
    unit: "%",
    basf: "",
    syn: "",
    tri: "",
    category: "Testing",
    dataType: "number",
  },
];

export const CUSTOMER_FEEDBACK_TARGET_VALUES: Record<string, string> = {
  "MH": "32",
  "Ts1": "1.8",
  "Ts2": "3.2",
  "T10": "2.5",
  "T50": "6.5",
  "T90": "12.0",
  "Hardness": "70",
  "Tensile Strength": "24",
  "Elongation at Break": "480",
  "Modulus @ 100": "3.2",
  "Modulus @ 300": "12.5",
  "Tear Strength": "145",
  "Abrasion": "110",
  "Compression Set": "22",
  "Ozone Resistance": "Pass",
  "Rebound Resilience": "48",
};

export interface OptimizedRecipeChange {
  parameter: string;
  previous: string;
  revised: string;
}

export interface OptimizedRecipeImpact {
  label: string;
  value: string;
}

export interface OptimizedRecipe {
  id: string;
  name: string;
  confidence: number;
  changes: OptimizedRecipeChange[];
  impacts: OptimizedRecipeImpact[];
}

export const OPTIMIZED_RECIPES: OptimizedRecipe[] = [
  {
    id: "recipe-2-rev-a",
    name: "Recipe 2 – Revision A",
    confidence: 89,
    changes: [
      {
        parameter: "Chain Transfer Agent",
        previous: "0.45 phr",
        revised: "0.60 phr",
      },
      { parameter: "Initiator", previous: "0.07 phr", revised: "0.05 phr" },
      {
        parameter: "Polymerization Temp",
        previous: "10°C",
        revised: "8°C",
      },
    ],
    impacts: [
      { label: "Hardness", value: "+3 Shore A" },
      { label: "Processing Oil", value: "12 → 8 phr" },
      { label: "Tensile Strength", value: "+1.8 MPa" },
      { label: "Mooney (ML1+4 @ 100°C)", value: "47 → 50" },
    ],
  },
  {
    id: "recipe-2-rev-b",
    name: "Recipe 2 – Revision B",
    confidence: 86,
    changes: [
      {
        parameter: "BD/ACN Ratio",
        previous: "70/30",
        revised: "68/32",
      },
      {
        parameter: "Emulsifier Loading",
        previous: "0.5 phr",
        revised: "0.8 phr",
      },
      {
        parameter: "Conversion Target",
        previous: "88%",
        revised: "85%",
      },
    ],
    impacts: [
      { label: "Hardness", value: "+2 Shore A" },
      { label: "Processing Oil", value: "12 → 9 phr" },
      { label: "Tensile Strength", value: "+1.2 MPa" },
      { label: "Mooney (ML1+4 @ 100°C)", value: "47 → 49" },
    ],
  },
  {
    id: "recipe-2-rev-c",
    name: "Recipe 2 – Revision C",
    confidence: 84,
    changes: [
      {
        parameter: "Chain Transfer Agent",
        previous: "0.45 phr",
        revised: "0.52 phr",
      },
      {
        parameter: "Coagulation pH",
        previous: "6.8",
        revised: "7.2",
      },
      {
        parameter: "Water",
        previous: "190 phr",
        revised: "185 phr",
      },
    ],
    impacts: [
      { label: "Hardness", value: "+1 Shore A" },
      { label: "Processing Oil", value: "12 → 10 phr" },
      { label: "Tensile Strength", value: "+0.9 MPa" },
      { label: "Mooney (ML1+4 @ 100°C)", value: "47 → 48" },
    ],
  },
];

export function buildInitialCompetitorValues(
  rows: SpecRowTemplate[],
): Record<string, { basf: string; syn: string; tri: string }> {
  return Object.fromEntries(
    rows.map((row) => [
      row.feature,
      { basf: row.basf, syn: row.syn, tri: row.tri },
    ]),
  );
}

export interface TransferredSpecData {
  competitorData: Array<{
    feature: string;
    unit: string;
    basf: string;
    syn: string;
    tri: string;
  }>;
  patentResearchData: Array<{
    feature: string;
    values: Record<string, string>;
  }>;
  targetPolymerProperties: Array<{
    feature: string;
    unit: string;
    range: { min: string; max: string };
  }>;
}
