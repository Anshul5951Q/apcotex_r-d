import type { PatentResearchReport } from "../../contexts/PatentResearchContext";
import type {
  SpecRowTemplate,
} from "./recipeSimulatorDemoData";

export const PATENT_SOURCE_COLUMN_MAP: Record<
  string,
  { key: string; label: string }
> = {
  USPTO: { key: "uspto", label: "USPTO" },
  Espacenet: { key: "espacenet", label: "Espacenet" },
  InPASS: { key: "inpass", label: "InPASS" },
};

export const DEFAULT_PATENT_SOURCES = ["USPTO", "Espacenet", "InPASS"];

export type { SpecRowTemplate };

export function getPatentColumns(
  recipeData: any, // Accepts the extracted JSON array
) {
  if (Array.isArray(recipeData) && recipeData.length > 0) {
    return recipeData.map((ext: any, idx: number) => ({
      source: ext.patent_title || `Patent ${idx + 1}`,
      key: `patent_${idx}`,
      label: ext.assignee || `Source ${idx + 1}`
    }));
  }

  // Fallback
  return DEFAULT_PATENT_SOURCES.map((source) => ({
    source,
    ...PATENT_SOURCE_COLUMN_MAP[source],
  }));
}

export function buildPatentColumnValues(
  recipeData: any,
  specRows: SpecRowTemplate[],
): Record<string, Record<string, string>> {
  const result: Record<string, Record<string, string>> = {};

  for (const row of specRows) {
    result[row.feature] = {};
    if (Array.isArray(recipeData) && recipeData.length > 0) {
      recipeData.forEach((ext: any, idx: number) => {
        const key = `patent_${idx}`;
        const prop = ext.extracted_properties?.find((p: any) => 
          p.feature.toLowerCase().includes(row.feature.toLowerCase()) || 
          row.feature.toLowerCase().includes(p.feature.toLowerCase())
        );
        result[row.feature][key] = prop ? prop.value : "N/A";
      });
    } else {
       // No data fallback
       result[row.feature] = {};
    }
  }

  return result;
}

export interface PatentRecipeStep {
  param: string;
  step: string;
  desc: string;
  temp: string;
  duration: string;
}

const PATENT_SOURCE_RECIPES: Record<string, PatentRecipeStep[]> = {
  uspto: [
    {
      param: "Monomer Charge",
      step: "PR#1",
      desc: "Charge butadiene/acrylonitrile at 72/28 per cold emulsion protocol (US20250075019A1)",
      temp: "25°C",
      duration: "15 min",
    },
    {
      param: "Water Addition",
      step: "PR#2",
      desc: "Add deionized water at 180 phr with high-shear dispersion",
      temp: "25°C",
      duration: "12 min",
    },
    {
      param: "Emulsifier",
      step: "PR#3",
      desc: "Add potassium oleate at 2.5 phr and stabilize emulsion",
      temp: "25°C",
      duration: "10 min",
    },
    {
      param: "Temperature Ramp",
      step: "PR#4",
      desc: "Ramp reactor to 10°C for cold-process polymerization",
      temp: "10°C",
      duration: "20 min",
    },
    {
      param: "Initiator",
      step: "PR#5",
      desc: "Dose potassium persulfate at 0.07 phr to initiate reaction",
      temp: "10°C",
      duration: "5 min",
    },
    {
      param: "Chain Transfer Agent",
      step: "PR#6",
      desc: "Add tert-dodecyl mercaptan at 0.55 phr for Mooney control",
      temp: "10°C",
      duration: "8 min",
    },
    {
      param: "Polymerization Hold",
      step: "PR#7",
      desc: "Maintain reaction until 85% conversion, terminate with hydroxylamine sulfate",
      temp: "10°C",
      duration: "420 min",
    },
    {
      param: "Coagulation",
      step: "PR#8",
      desc: "Coagulate with 1.8 wt% calcium chloride after antioxidant addition",
      temp: "65°C",
      duration: "45 min",
    },
    {
      param: "Washing & Drying",
      step: "PR#9",
      desc: "Wash crumbs and dry at 100°C to release raw polymer",
      temp: "100°C",
      duration: "90 min",
    },
    {
      param: "Quality Release",
      step: "PR#10",
      desc: "Verify bound ACN, Mooney viscosity, and volatile matter against patent targets",
      temp: "25°C",
      duration: "20 min",
    },
  ],
  espacenet: [
    {
      param: "Monomer Charge",
      step: "PR#1",
      desc: "Charge butadiene/acrylonitrile at 72/28 per LG Chem cold emulsion method (EP3892656A1)",
      temp: "25°C",
      duration: "15 min",
    },
    {
      param: "Water Addition",
      step: "PR#2",
      desc: "Add deionized water at 190 phr",
      temp: "25°C",
      duration: "12 min",
    },
    {
      param: "Emulsifier",
      step: "PR#3",
      desc: "Add sulfosuccinate ester / fatty acid mixture at 1.2 phr",
      temp: "25°C",
      duration: "10 min",
    },
    {
      param: "Temperature Ramp",
      step: "PR#4",
      desc: "Ramp reactor to 10°C",
      temp: "10°C",
      duration: "20 min",
    },
    {
      param: "Initiator",
      step: "PR#5",
      desc: "Dose p-menthane hydroperoxide at 0.04 phr",
      temp: "10°C",
      duration: "5 min",
    },
    {
      param: "Chain Transfer Agent",
      step: "PR#6",
      desc: "Add t-dodecyl mercaptan at 0.5 phr",
      temp: "10°C",
      duration: "8 min",
    },
    {
      param: "Polymerization Hold",
      step: "PR#7",
      desc: "Maintain emulsion polymerization until target conversion",
      temp: "10°C",
      duration: "390 min",
    },
    {
      param: "Coagulation",
      step: "PR#8",
      desc: "Coagulate with CaCl2 aqueous solution at 50–70°C",
      temp: "60°C",
      duration: "45 min",
    },
    {
      param: "Drying",
      step: "PR#9",
      desc: "Dry polymer at 80–130°C to minimize residual emulsifier",
      temp: "110°C",
      duration: "90 min",
    },
    {
      param: "Quality Release",
      step: "PR#10",
      desc: "Confirm low residual emulsifier and target Mooney viscosity",
      temp: "25°C",
      duration: "20 min",
    },
  ],
  inpass: [
    {
      param: "Monomer Charge",
      step: "PR#1",
      desc: "Charge butadiene/acrylonitrile at 66/34 with divided ACN addition strategy",
      temp: "25°C",
      duration: "15 min",
    },
    {
      param: "Water Addition",
      step: "PR#2",
      desc: "Add deionized water at 190 phr with moderate shear mixing",
      temp: "25°C",
      duration: "12 min",
    },
    {
      param: "Emulsifier",
      step: "PR#3",
      desc: "Add sulfonate-based emulsifier and fatty acid system",
      temp: "25°C",
      duration: "10 min",
    },
    {
      param: "Temperature Ramp",
      step: "PR#4",
      desc: "Ramp reactor to 10°C for cold emulsion polymerization",
      temp: "10°C",
      duration: "20 min",
    },
    {
      param: "Initiator",
      step: "PR#5",
      desc: "Dose initiator at 0.03–0.05 phr",
      temp: "10°C",
      duration: "5 min",
    },
    {
      param: "Chain Transfer Agent",
      step: "PR#6",
      desc: "Add chain transfer agent at 0.5 phr",
      temp: "10°C",
      duration: "8 min",
    },
    {
      param: "Polymerization Hold",
      step: "PR#7",
      desc: "Maintain reaction to ≥80% conversion",
      temp: "10°C",
      duration: "400 min",
    },
    {
      param: "Coagulation",
      step: "PR#8",
      desc: "Coagulate with colloidal sulfur at 50–80°C and alkaline wash",
      temp: "65°C",
      duration: "45 min",
    },
    {
      param: "Drying",
      step: "PR#9",
      desc: "Wash and dry to target Mooney and resilience properties",
      temp: "100°C",
      duration: "90 min",
    },
    {
      param: "Quality Release",
      step: "PR#10",
      desc: "Release batch after Mooney and low-temperature characteristic checks",
      temp: "25°C",
      duration: "20 min",
    },
  ],
};

export function getPatentSourceRecipeSteps(
  columnKey: string,
): PatentRecipeStep[] {
  return PATENT_SOURCE_RECIPES[columnKey] ?? PATENT_SOURCE_RECIPES.uspto;
}
