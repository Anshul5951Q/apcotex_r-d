import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { CheckCircle2 } from "lucide-react";
import { usePatentResearch } from "../../contexts/PatentResearchContext";
import type { PatentResearchReport } from "../../contexts/PatentResearchContext";
import {
  DEFAULT_CUSTOMER_FEEDBACK,
  POLYMERIZATION_RECIPES,
  convertToEditableRecipe,
  type EditableRecipe,
  type RecipeProperty,
  type TransferredSpecData,
} from "./recipeSimulatorDemoData";
import {
  Step1TargetSpec,
  Step2PolymerizationRecommendations,
  Step3CustomerTrialFeedback,
  Step4OptimizedRecipes,
} from "./RecipeSimulatorSteps";

const BLUE = "#1F5FA8";
const TEAL = "#1FB7B5";

const STEPS = [
  { num: 1, label: "Define Target Polymer Specification" },
  { num: 2, label: "Polymerization Recipe Recommendations" },
  { num: 3, label: "Customer Trial Feedback" },
  { num: 4, label: "Optimized Polymerization Recipes" },
];

function Stepper({ current }: { current: number }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 0,
        marginBottom: 28,
        overflowX: "auto",
      }}
    >
      {STEPS.map((step, i) => {
        const done = current > step.num;
        const active = current === step.num;
        return (
          <div
            key={step.num}
            style={{
              display: "flex",
              alignItems: "center",
              flex: i < STEPS.length - 1 ? 1 : undefined,
              minWidth: 0,
            }}
          >
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 6,
                minWidth: 120,
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: "50%",
                  background: done ? TEAL : active ? BLUE : "#E5E7EB",
                  color: done || active ? "white" : "#9CA3AF",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 700,
                  fontSize: "0.875rem",
                  flexShrink: 0,
                }}
              >
                {done ? (
                  <CheckCircle2 size={16} strokeWidth={2.5} />
                ) : (
                  step.num
                )}
              </div>
              <span
                style={{
                  fontSize: "0.7rem",
                  color: done ? TEAL : active ? BLUE : "#9CA3AF",
                  fontWeight: active ? 600 : 500,
                  textAlign: "center",
                  lineHeight: 1.3,
                  maxWidth: 130,
                }}
              >
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                style={{
                  flex: 1,
                  height: 2,
                  background: done ? TEAL : "#E5E7EB",
                  margin: "0 8px",
                  marginBottom: 22,
                  minWidth: 24,
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export function RecipeSimulator() {
  const navigate = useNavigate();
  const { state } = usePatentResearch();
  const recipeData = state.recipeData;
  const [step, setStep] = useState(1);
  const [transferredData, setTransferredData] =
    useState<TransferredSpecData | null>(null);
  const [selectedRecipeId, setSelectedRecipeId] = useState("recipe-2");
  const [patentResearchInput, setPatentResearchInput] =
    useState<any | null>(recipeData);
  const [editableRecipes, setEditableRecipes] = useState<EditableRecipe[]>(() =>
    POLYMERIZATION_RECIPES.map(convertToEditableRecipe)
  );

  const updateRecipeProperty = (recipeId: string, propertyId: string, updates: Partial<RecipeProperty>) => {
    setEditableRecipes((prev) =>
      prev.map((r) =>
        r.id === recipeId
          ? {
              ...r,
              properties: r.properties.map((p) =>
                p.id === propertyId ? { ...p, ...updates } : p
              ),
            }
          : r
      )
    );
  };

  const addRecipeProperty = (recipeId: string, property: RecipeProperty) => {
    setEditableRecipes((prev) =>
      prev.map((r) =>
        r.id === recipeId
          ? { ...r, properties: [...r.properties, property] }
          : r
      )
    );
  };

  const deleteRecipeProperty = (recipeId: string, propertyId: string) => {
    setEditableRecipes((prev) =>
      prev.map((r) =>
        r.id === recipeId
          ? {
              ...r,
              properties: r.properties.filter((p) => p.id !== propertyId),
            }
          : r
      )
    );
  };

  const resetRecipe = (recipeId: string) => {
    const original = POLYMERIZATION_RECIPES.find((r) => r.id === recipeId);
    if (original) {
      setEditableRecipes((prev) =>
        prev.map((r) =>
          r.id === recipeId ? convertToEditableRecipe(original) : r
        )
      );
    }
  };

  useEffect(() => {
    if (recipeData) {
      setPatentResearchInput(recipeData);
    } else {
      setPatentResearchInput(null);
    }
  }, [recipeData]);

  const selectedRecipe =
    editableRecipes.find((recipe) => recipe.id === selectedRecipeId) ??
    editableRecipes[1];

  return (
    <div style={{ padding: "28px 32px 48px" }}>
      <div style={{ marginBottom: 24 }}>
        <h1
          style={{
            color: BLUE,
            fontSize: "1.25rem",
            fontWeight: 700,
            marginBottom: 4,
          }}
        >
          Recipe Simulator
        </h1>
        <p style={{ color: "#6B7280", fontSize: "0.875rem" }}>
          AI-powered formulation prediction · Step {step} of {STEPS.length}
        </p>
      </div>

      <Stepper current={step} />

      {step === 1 && (
        <Step1TargetSpec
          onBack={() => navigate("/literature-review")}
          onContinue={(data) => {
            setTransferredData(data);
            setStep(2);
          }}
          transferredData={transferredData}
          patentResearchReport={patentResearchInput}
        />
      )}

      {step === 2 && (
        <Step2PolymerizationRecommendations
          onBack={() => setStep(1)}
          onContinue={() => setStep(3)}
          selectedRecipeId={selectedRecipeId}
          onSelectRecipe={setSelectedRecipeId}
          recipes={editableRecipes}
          onUpdateProperty={updateRecipeProperty}
          onAddProperty={addRecipeProperty}
          onDeleteProperty={deleteRecipeProperty}
          onResetRecipe={resetRecipe}
        />
      )}

      {step === 3 && (
        <Step3CustomerTrialFeedback
          onBack={() => setStep(2)}
          onOptimize={() => setStep(4)}
          selectedRecipeName={selectedRecipe.name}
          transferredData={transferredData}
        />
      )}

      {step === 4 && (
        <Step4OptimizedRecipes onBack={() => setStep(3)} />
      )}
    </div>
  );
}
