import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { CheckCircle2, History } from "lucide-react";
import { usePatentResearch } from "../../contexts/PatentResearchContext";
import { useRecipe } from "../../contexts/RecipeContext";
import {
  Step1TargetSpec,
  Step2PolymerizationRecommendations,
  Step3CustomerTrialFeedback,
  Step4OptimizedRecipes,
} from "./RecipeSimulatorSteps";
import { TransferredSpecData } from "./recipeSimulatorDemoData";

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
  const { state: researchState } = usePatentResearch();
  
  const { 
    cycle, 
    resetContext, 
    error
  } = useRecipe();

  // Local state for the UI step (driven by cycle status if loaded)
  const [step, setStep] = useState(1);

  // Sync step with cycle status
  useEffect(() => {
    if (!cycle) {
      setStep(1);
    } else {
      switch (cycle.status) {
        case "PENDING":
        case "STEP1":
        case "GENERATING":
          setStep(2); // If we're generating or have entered step 1, proceed to 2
          break;
        case "STEP2":
          setStep(2);
          break;
        case "STEP3":
        case "OPTIMIZING":
          setStep(3);
          break;
        case "STEP4":
        case "COMPLETED":
          setStep(4);
          break;
        default:
          setStep(1);
      }
    }
  }, [cycle]);

  return (
    <div style={{ padding: "28px 32px 48px" }}>
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
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
        
        <div style={{ display: 'flex', gap: 12 }}>
          <button
            onClick={() => navigate('/recipe-history')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              background: 'white',
              border: `1px solid #E5E7EB`,
              borderRadius: 6,
              padding: '8px 16px',
              fontSize: '0.875rem',
              fontWeight: 600,
              color: '#374151',
              cursor: 'pointer'
            }}
          >
            <History size={16} />
            Previous Recipes
          </button>
          
          <button
            onClick={() => {
              if(confirm("Start a new recipe simulation? Unsaved progress will be lost.")) {
                resetContext();
                setStep(1);
              }
            }}
            style={{
              background: TEAL,
              border: 'none',
              borderRadius: 6,
              padding: '8px 16px',
              fontSize: '0.875rem',
              fontWeight: 600,
              color: 'white',
              cursor: 'pointer'
            }}
          >
            Generate New Recipe
          </button>
        </div>
      </div>

      <Stepper current={step} />
      
      {error && (
        <div style={{ background: '#FEE2E2', border: '1px solid #FCA5A5', color: '#991B1B', padding: 12, borderRadius: 6, marginBottom: 24 }}>
          {error}
        </div>
      )}

      {step === 1 && (
        <Step1TargetSpec
          onBack={() => navigate("/literature-review")}
          onContinue={() => setStep(2)}
        />
      )}

      {step === 2 && (
        <Step2PolymerizationRecommendations
          onBack={() => setStep(1)}
          onContinue={() => setStep(3)}
        />
      )}

      {step === 3 && (
        <Step3CustomerTrialFeedback
          onBack={() => setStep(2)}
          onOptimize={() => setStep(4)}
        />
      )}

      {step === 4 && (
        <Step4OptimizedRecipes 
          onBack={() => setStep(3)} 
        />
      )}
    </div>
  );
}
