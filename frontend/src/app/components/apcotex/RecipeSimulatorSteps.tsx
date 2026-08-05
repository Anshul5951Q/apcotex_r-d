import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import {
  ChevronLeft,
  ChevronRight,
  Loader,
  Sparkles,
  Trophy,
  Plus,
  Trash2,
  Edit2,
  CheckCircle2,
} from "lucide-react";
// Removed PatentResearchReport import
import type { PatentRecipeStep } from "./recipeSimulatorPatentData";
import {
  buildPatentColumnValues,
  getPatentColumns,
  getPatentSourceRecipeSteps,
} from "./recipeSimulatorPatentData";
import {
  buildInitialCompetitorValues,
  CUSTOMER_FEEDBACK_PROPERTIES,
  CUSTOMER_FEEDBACK_TARGET_VALUES,
  DEFAULT_CUSTOMER_FEEDBACK,
  DEMO_CUSTOMER_NOTES,
  DEMO_TARGET_VALUES,
  getPolymerizationRecipeSteps,
  OPTIMIZED_RECIPES,
  POLYMERIZATION_RECIPES,
  type CustomerFeedbackOption,
  type OptimizedRecipe,
  type PolymerizationRecipe,
  type EditableRecipe,
  type RecipeProperty,
  type TransferredSpecData,
  type SpecRowTemplate,
} from "./recipeSimulatorDemoData";
import { LowAcnPatentReportViewer } from "./LowAcnPatentReportViewer";
import { useProperties } from "../../contexts/PropertyContext";
import { CustomerFeedbackProvider, useCustomerFeedbackProperties } from "../../contexts/CustomerFeedbackContext";

const BLUE = "#1F5FA8";
const TEAL = "#1FB7B5";
const RED = "#D93A2F";
const TEXT = "#1F2937";
const BORDER = "#E5E7EB";
const BG = "#F7FAFC";

const card = {
  background: "white",
  border: `1px solid ${BORDER}`,
  borderRadius: 8,
  boxShadow: "0 1px 3px rgba(31,95,168,0.06)",
};

function RecipeDetailTable({
  title,
  steps,
}: {
  title: string;
  steps: PatentRecipeStep[];
}) {
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ ...card, overflow: "hidden" }}>
        <div
          style={{
            padding: "12px 16px",
            borderBottom: `1px solid ${BORDER}`,
            background: "rgba(31,95,168,0.07)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span style={{ fontSize: "0.875rem", fontWeight: 600, color: TEXT }}>
            {title}
          </span>
          <span style={{ fontSize: "0.75rem", color: "#9CA3AF" }}>
            PR#01–PR#10
          </span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              borderCollapse: "collapse",
              minWidth: 600,
              width: "100%",
            }}
          >
            <thead>
              <tr style={{ background: BG }}>
                {[
                  "Parameter",
                  "Step ID",
                  "Recipe Description",
                  "Temperature",
                  "Duration",
                ].map((h, i) => (
                  <th
                    key={h}
                    style={{
                      padding: "10px 14px",
                      textAlign: i === 0 ? "left" : "center",
                      fontSize: "0.75rem",
                      fontWeight: 700,
                      color: BLUE,
                      borderBottom: `1.5px solid ${BORDER}`,
                      borderRight: `1px solid ${BORDER}`,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {steps.map((row, i) => (
                <tr
                  key={row.step}
                  style={{
                    borderTop: `1px solid ${BORDER}`,
                    background: i % 2 === 0 ? "white" : "rgba(247,250,252,0.5)",
                  }}
                >
                  <td
                    style={{
                      padding: "10px 14px",
                      fontSize: "0.8125rem",
                      color: TEXT,
                      fontWeight: 500,
                      borderRight: `1px solid ${BORDER}`,
                    }}
                  >
                    {row.param}
                  </td>
                  <td
                    style={{
                      padding: "10px 14px",
                      fontSize: "0.8125rem",
                      color: BLUE,
                      fontWeight: 600,
                      textAlign: "center",
                      borderRight: `1px solid ${BORDER}`,
                    }}
                  >
                    {row.step}
                  </td>
                  <td
                    style={{
                      padding: "10px 14px",
                      fontSize: "0.8125rem",
                      color: TEXT,
                      borderRight: `1px solid ${BORDER}`,
                      lineHeight: 1.4,
                    }}
                  >
                    {row.desc}
                  </td>
                  <td
                    style={{
                      padding: "10px 14px",
                      fontSize: "0.8125rem",
                      textAlign: "center",
                      borderRight: `1px solid ${BORDER}`,
                    }}
                  >
                    {row.temp}
                  </td>
                  <td
                    style={{
                      padding: "10px 14px",
                      fontSize: "0.8125rem",
                      textAlign: "center",
                    }}
                  >
                    {row.duration}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function EditableRecipeDetailTable({
  recipe,
  onUpdateProperty,
  onAddProperty,
  onDeleteProperty,
  onResetRecipe,
}: {
  recipe: EditableRecipe;
  onUpdateProperty: (recipeId: string, propertyId: string, updates: Partial<RecipeProperty>) => void;
  onAddProperty: (recipeId: string, property: RecipeProperty) => void;
  onDeleteProperty: (recipeId: string, propertyId: string) => void;
  onResetRecipe: (recipeId: string) => void;
}) {
  const [editingPropertyId, setEditingPropertyId] = useState<string | null>(null);
  const [showAddProperty, setShowAddProperty] = useState(false);
  const [newProperty, setNewProperty] = useState({ name: "", value: "", unit: "" });

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: "0.875rem", color: "#6B7280", lineHeight: 1.5 }}>
          <strong style={{ color: BLUE }}>Patent Support:</strong> {recipe.patentSupport}
        </div>
        <button
          onClick={() => {
            if (confirm("Are you sure you want to reset this recipe to its AI recommendation?")) {
              onResetRecipe(recipe.id);
            }
          }}
          style={{
            background: "white",
            color: RED,
            border: `1px solid ${BORDER}`,
            borderRadius: 6,
            padding: "6px 12px",
            fontSize: "0.75rem",
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Reset to AI Recommendation
        </button>
      </div>

      <div style={{ ...card, overflow: "hidden" }}>
        <div
          style={{
            padding: "12px 16px",
            borderBottom: `1px solid ${BORDER}`,
            background: "rgba(31,95,168,0.07)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span style={{ fontSize: "0.875rem", fontWeight: 600, color: TEXT }}>
            Editable Formulation Properties
          </span>
        </div>
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              borderCollapse: "collapse",
              minWidth: 600,
              width: "100%",
            }}
          >
            <thead>
              <tr style={{ background: BG }}>
                {["Property Name", "Value", "Unit", "Actions"].map((h, i) => (
                  <th
                    key={h}
                    style={{
                      padding: "10px 14px",
                      textAlign: i === 0 ? "left" : "center",
                      fontSize: "0.75rem",
                      fontWeight: 700,
                      color: BLUE,
                      borderBottom: `1.5px solid ${BORDER}`,
                      borderRight: i < 3 ? `1px solid ${BORDER}` : "none",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recipe.properties.map((row, i) => (
                <tr
                  key={row.id}
                  style={{
                    borderTop: `1px solid ${BORDER}`,
                    background: i % 2 === 0 ? "white" : "rgba(247,250,252,0.5)",
                  }}
                >
                  <td
                    style={{
                      padding: "10px 14px",
                      fontSize: "0.8125rem",
                      color: TEXT,
                      fontWeight: 500,
                      borderRight: `1px solid ${BORDER}`,
                    }}
                  >
                    {editingPropertyId === row.id ? (
                      <input
                        type="text"
                        value={row.name}
                        onChange={(e) => onUpdateProperty(recipe.id, row.id, { name: e.target.value })}
                        onBlur={() => setEditingPropertyId(null)}
                        onKeyDown={(e) => e.key === 'Enter' && setEditingPropertyId(null)}
                        autoFocus
                        style={{
                          width: '100%',
                          border: '1px solid #E5E7EB',
                          borderRadius: 4,
                          padding: '4px 8px',
                          fontSize: '0.8125rem',
                          fontFamily: 'inherit',
                        }}
                      />
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ flex: 1 }}>{row.name}</span>
                        <button
                          onClick={() => setEditingPropertyId(row.id)}
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9CA3AF', padding: 2 }}
                        >
                          <Edit2 size={14} />
                        </button>
                      </div>
                    )}
                  </td>
                  <td
                    style={{
                      padding: "10px 14px",
                      borderRight: `1px solid ${BORDER}`,
                    }}
                  >
                    <input
                      type="text"
                      value={row.value}
                      onChange={(e) => onUpdateProperty(recipe.id, row.id, { value: e.target.value })}
                      style={{
                        width: "100%",
                        border: "1px solid #E5E7EB",
                        background: "white",
                        fontSize: "0.8125rem",
                        color: TEXT,
                        outline: "none",
                        fontFamily: "inherit",
                        textAlign: "center",
                        padding: "4px 6px",
                        borderRadius: "4px",
                        boxSizing: "border-box",
                      }}
                    />
                  </td>
                  <td
                    style={{
                      padding: "10px 14px",
                      borderRight: `1px solid ${BORDER}`,
                    }}
                  >
                    <input
                      type="text"
                      value={row.unit || ""}
                      onChange={(e) => onUpdateProperty(recipe.id, row.id, { unit: e.target.value })}
                      style={{
                        width: "100%",
                        border: "1px solid #E5E7EB",
                        background: "white",
                        fontSize: "0.8125rem",
                        color: TEXT,
                        outline: "none",
                        fontFamily: "inherit",
                        textAlign: "center",
                        padding: "4px 6px",
                        borderRadius: "4px",
                        boxSizing: "border-box",
                      }}
                    />
                  </td>
                  <td
                    style={{
                      padding: "10px 14px",
                      textAlign: "center",
                    }}
                  >
                    <button
                      onClick={() => {
                        if (confirm(`Are you sure you want to delete "${row.name}"?`)) {
                          onDeleteProperty(recipe.id, row.id);
                        }
                      }}
                      style={{
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: '#EF4444',
                        padding: 2,
                      }}
                      title="Delete property"
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
              {showAddProperty && (
                <tr style={{ borderTop: `1px solid ${BORDER}`, background: "rgba(31,183,181,0.03)" }}>
                  <td style={{ padding: "8px 12px", borderRight: `1px solid ${BORDER}` }}>
                    <input
                      type="text"
                      placeholder="Property Name"
                      value={newProperty.name}
                      onChange={(e) => setNewProperty(prev => ({ ...prev, name: e.target.value }))}
                      style={{
                        width: '100%',
                        border: '1px solid #E5E7EB',
                        borderRadius: 4,
                        padding: '6px 8px',
                        fontSize: '0.8125rem',
                        fontFamily: 'inherit',
                      }}
                    />
                  </td>
                  <td style={{ padding: "8px 12px", borderRight: `1px solid ${BORDER}` }}>
                    <input
                      type="text"
                      placeholder="Value"
                      value={newProperty.value}
                      onChange={(e) => setNewProperty(prev => ({ ...prev, value: e.target.value }))}
                      style={{
                        width: '100%',
                        border: '1px solid #E5E7EB',
                        borderRadius: 4,
                        padding: '6px 8px',
                        fontSize: '0.8125rem',
                        fontFamily: 'inherit',
                      }}
                    />
                  </td>
                  <td style={{ padding: "8px 12px", borderRight: `1px solid ${BORDER}` }}>
                    <input
                      type="text"
                      placeholder="Unit (optional)"
                      value={newProperty.unit}
                      onChange={(e) => setNewProperty(prev => ({ ...prev, unit: e.target.value }))}
                      style={{
                        width: '100%',
                        border: '1px solid #E5E7EB',
                        borderRadius: 4,
                        padding: '6px 8px',
                        fontSize: '0.8125rem',
                        fontFamily: 'inherit',
                      }}
                    />
                  </td>
                  <td style={{ padding: "8px 12px", textAlign: "center" }}>
                    <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
                      <button
                        onClick={() => {
                          if (newProperty.name.trim()) {
                            onAddProperty(recipe.id, {
                              id: `custom-prop-${Date.now()}`,
                              name: newProperty.name,
                              value: newProperty.value,
                              unit: newProperty.unit,
                            });
                            setNewProperty({ name: '', value: '', unit: '' });
                            setShowAddProperty(false);
                          }
                        }}
                        style={{
                          background: TEAL,
                          color: 'white',
                          border: 'none',
                          borderRadius: 4,
                          padding: '6px 12px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        Save
                      </button>
                      <button
                        onClick={() => {
                          setShowAddProperty(false);
                          setNewProperty({ name: '', value: '', unit: '' });
                        }}
                        style={{
                          background: '#E5E7EB',
                          color: '#374151',
                          border: 'none',
                          borderRadius: 4,
                          padding: '6px 12px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
            <tfoot>
              {!showAddProperty && (
                <tr>
                  <td
                    colSpan={4}
                    style={{
                      borderTop: `1px solid ${BORDER}`,
                      padding: '12px',
                      textAlign: 'center',
                    }}
                  >
                    <button
                      onClick={() => setShowAddProperty(true)}
                      style={{
                        background: 'rgba(31,183,181,0.1)',
                        color: TEAL,
                        border: `1px dashed ${TEAL}`,
                        borderRadius: 6,
                        padding: '8px 16px',
                        fontSize: '0.8125rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        margin: '0 auto',
                      }}
                    >
                      <Plus size={16} />
                      Add Property
                    </button>
                  </td>
                </tr>
              )}
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  );
}

function PolymerizationRecipeCard({
  recipe,
  selected,
  onSelect,
  onUpdateProperty,
  onAddProperty,
  onDeleteProperty,
  onResetRecipe,
}: {
  recipe: EditableRecipe;
  selected: boolean;
  onSelect: () => void;
  onUpdateProperty: (recipeId: string, propertyId: string, updates: Partial<RecipeProperty>) => void;
  onAddProperty: (recipeId: string, property: RecipeProperty) => void;
  onDeleteProperty: (recipeId: string, propertyId: string) => void;
  onResetRecipe: (recipeId: string) => void;
}) {
  const [showRecipe, setShowRecipe] = useState(false);

  return (
    <div
      style={{
        ...card,
        borderTop: selected
          ? `3px solid ${TEAL}`
          : `3px solid transparent`,
        position: "relative",
        flex: "1 1 220px",
        minWidth: 220,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div style={{ padding: "16px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 10,
          }}
        >
          <span style={{ fontSize: "0.9375rem", fontWeight: 700, color: BLUE }}>
            {recipe.name}
          </span>
          <span
            style={{
              background: "rgba(31,183,181,0.12)",
              color: TEAL,
              fontWeight: 700,
              fontSize: "0.8125rem",
              padding: "3px 10px",
              borderRadius: 20,
            }}
          >
            {recipe.confidence}%
          </span>
        </div>

        <div
          style={{
            background: BG,
            borderRadius: 6,
            padding: "10px",
            marginBottom: 12,
            fontSize: "0.75rem",
            color: TEXT,
            lineHeight: 1.6,
          }}
        >
          {recipe.properties.map((prop) => (
            <div key={prop.id}>
              <strong>{prop.name}:</strong> {prop.value} {prop.unit}
            </div>
          ))}
        </div>

        <div
          style={{
            fontSize: "0.75rem",
            color: "#6B7280",
            marginBottom: 12,
            lineHeight: 1.5,
          }}
        >
          <strong style={{ color: BLUE }}>Patent Support:</strong>{" "}
          {recipe.patentSupport}
        </div>

        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={onSelect}
            style={{
              flex: 1,
              border: `1.5px solid ${selected ? TEAL : BORDER}`,
              color: selected ? TEAL : BLUE,
              background: selected ? "rgba(31,183,181,0.08)" : "white",
              borderRadius: 6,
              padding: "8px 0",
              fontSize: "0.8125rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {selected ? "Selected" : "Select"}
          </button>
          <button
            onClick={() => setShowRecipe((v) => !v)}
            style={{
              flex: 1,
              background: BLUE,
              color: "white",
              border: "none",
              borderRadius: 6,
              padding: "8px 0",
              fontSize: "0.8125rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            {showRecipe ? "Hide Recipe" : "View Recipe"}
          </button>
        </div>
      </div>

      {showRecipe && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
          <div style={{ backgroundColor: 'white', borderRadius: 8, padding: '24px', maxWidth: '800px', width: '100%', maxHeight: '90vh', overflowY: 'auto', position: 'relative' }}>
            <button onClick={() => setShowRecipe(false)} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.5rem', lineHeight: 1 }}>&times;</button>
            <h3 style={{ margin: "0 0 16px 0", color: BLUE, fontSize: "1.125rem", fontWeight: 700 }}>
              {recipe.name} - Polymerization Recipe Details
            </h3>
            <EditableRecipeDetailTable
              recipe={recipe}
              onUpdateProperty={onUpdateProperty}
              onAddProperty={onAddProperty}
              onDeleteProperty={onDeleteProperty}
              onResetRecipe={onResetRecipe}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export function Step1TargetSpec({
  onBack,
  onContinue,
  transferredData,
  patentResearchReport,
}: {
  onBack: () => void;
  onContinue: (data: TransferredSpecData) => void;
  transferredData?: TransferredSpecData | null;
  patentResearchReport?: any | null;
}) {
  const { properties, addProperty, updateProperty, deleteProperty } = useProperties();
  const [showPatentReport, setShowPatentReport] = useState(false);
  const patentColumns = getPatentColumns(patentResearchReport);
  const [desired, setDesired] = useState<
    Record<string, { min: string; max: string }>
  >(() => {
    if (!transferredData?.targetPolymerProperties) return {};
    return Object.fromEntries(
      transferredData.targetPolymerProperties.map((item) => [
        item.feature,
        item.range,
      ]),
    );
  });
  const [competitorValues, setCompetitorValues] = useState<
    Record<string, { basf: string; syn: string; tri: string }>
  >(() =>
    transferredData?.competitorData
      ? Object.fromEntries(
        transferredData.competitorData.map((item) => [
          item.feature,
          { basf: item.basf, syn: item.syn, tri: item.tri },
        ]),
      )
      : buildInitialCompetitorValues(properties),
  );
  const patentValues = useMemo(() => {
    if (transferredData?.patentResearchData) {
      return Object.fromEntries(
        transferredData.patentResearchData.map((item) => [
          item.feature,
          item.values,
        ]),
      );
    }
    return buildPatentColumnValues(patentResearchReport, properties);
  }, [patentResearchReport, transferredData, properties]);
  const [running, setRunning] = useState(false);
  const [showPatentRecipes, setShowPatentRecipes] = useState<
    Record<string, boolean>
  >({});
  const [showAddProperty, setShowAddProperty] = useState(false);
  const [editingProperty, setEditingProperty] = useState<string | null>(null);
  const [newProperty, setNewProperty] = useState({
    feature: '',
    unit: '',
    category: '',
    dataType: 'number' as 'number' | 'text' | 'boolean',
  });

  useEffect(() => {
    if (transferredData) return;
    setCompetitorValues(buildInitialCompetitorValues(properties));
  }, [patentResearchReport, transferredData, properties]);

  const handleRun = () => {
    setRunning(true);
    setTimeout(() => {
      setRunning(false);
      onContinue({
        competitorData: properties.map((row) => ({
          feature: row.feature,
          unit: row.unit,
          basf: competitorValues[row.feature]?.basf ?? row.basf,
          syn: competitorValues[row.feature]?.syn ?? row.syn,
          tri: competitorValues[row.feature]?.tri ?? row.tri,
        })),
        patentResearchData: properties.map((row) => ({
          feature: row.feature,
          values: patentValues[row.feature] ?? {},
        })),
        targetPolymerProperties: properties.map((row) => ({
          feature: row.feature,
          unit: row.unit,
          range: desired[row.feature] || { min: "", max: "" },
        })),
      });
    }, 1800);
  };

  const readOnlyCell = {
    padding: "8px 12px",
    fontSize: "0.8125rem",
    color: "#374151",
    background: "#F9FAFB",
    textAlign: "right" as const,
    fontVariantNumeric: "tabular-nums" as const,
    borderRight: `1px solid ${BORDER}`,
  };

  const patentCell = {
    ...readOnlyCell,
    background: "#F3F4F6",
    color: "#4B5563",
  };

  const editableInputStyle = {
    width: "100%",
    border: "1px solid #E5E7EB",
    background: "white",
    fontSize: "0.8125rem",
    color: TEXT,
    outline: "none",
    fontFamily: "inherit",
    textAlign: "right" as const,
    fontVariantNumeric: "tabular-nums" as const,
    padding: "4px 6px",
    borderRadius: "4px",
    boxSizing: "border-box" as const,
  };

  const headerCell = {
    padding: "9px 12px",
    fontSize: "0.75rem",
    fontWeight: 700,
    color: BLUE,
    background: BG,
    textAlign: "right" as const,
    whiteSpace: "nowrap" as const,
    borderRight: `1px solid ${BORDER}`,
    borderBottom: `1px solid ${BORDER}`,
  };

  return (
    <div>
      <div style={{ overflowX: "auto" }}>
        <div style={{ ...card, overflow: "hidden", minWidth: "fit-content" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              minWidth: 1100,
              tableLayout: "fixed",
            }}
          >
            <colgroup>
              <col style={{ width: "340px" }} />
              <col style={{ width: "95px" }} />
              <col style={{ width: "95px" }} />
              <col style={{ width: "95px" }} />
              <col style={{ width: "320px" }} />
              <col style={{ width: "auto", minWidth: "220px" }} />
            </colgroup>
            <thead>
              <tr>
                <th
                  style={{
                    ...headerCell,
                    textAlign: "left",
                    background: "white",
                  }}
                />
                <th
                  colSpan={3}
                  style={{
                    padding: "9px 12px",
                    fontSize: "0.75rem",
                    fontWeight: 800,
                    color: BLUE,
                    background: "rgba(31,95,168,0.07)",
                    textAlign: "center",
                    borderBottom: `1px solid ${BORDER}`,
                    borderRight: `1px solid ${BORDER}`,
                    textTransform: "uppercase",
                  }}
                >
                  Competitor Product Properties
                </th>
                <th
                  rowSpan={2}
                  style={{
                    padding: "9px 12px",
                    fontSize: "0.75rem",
                    fontWeight: 800,
                    color: "#6B7280",
                    background: "#F3F4F6",
                    textAlign: "center",
                    borderBottom: `1px solid ${BORDER}`,
                    borderRight: `1px solid ${BORDER}`,
                    textTransform: "uppercase",
                    width: 320,
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: '0 16px' }}>
                    <div style={{ marginBottom: 4 }}>Patent Research Data</div>
                    <div style={{ fontSize: '0.7rem', fontWeight: 500, color: '#9CA3AF', textTransform: 'none', marginBottom: 12, lineHeight: 1.4, textAlign: 'center' }}>
                      View the generated Patent Research Report used to populate this simulator.
                    </div>
                    <button
                      onClick={() => setShowPatentReport(true)}
                      style={{
                        background: TEAL,
                        color: "white",
                        border: "none",
                        borderRadius: 6,
                        padding: "8px 18px",
                        fontSize: "0.8125rem",
                        fontWeight: 600,
                        cursor: "pointer",
                        textTransform: "none",
                      }}
                    >
                      View Patent Report
                    </button>
                  </div>
                </th>
                <th
                  style={{
                    padding: "9px 12px",
                    fontSize: "0.75rem",
                    fontWeight: 800,
                    color: TEAL,
                    background: "rgba(31,183,181,0.10)",
                    textAlign: "center",
                    borderBottom: `1px solid ${BORDER}`,
                    borderLeft: `2px solid ${TEAL}`,
                    textTransform: "uppercase",
                  }}
                >
                  Target Polymer Properties
                </th>
              </tr>
              <tr>
                <th style={{ ...headerCell, textAlign: "left" }}>
                  Property
                </th>
                <th style={headerCell}>BASF</th>
                <th style={headerCell}>Synthomer</th>
                <th style={headerCell}>Trinseo</th>
                {/* patentColumns removed */}
                <th
                  style={{
                    ...headerCell,
                    background: "rgba(31,183,181,0.08)",
                    borderLeft: `2px solid ${TEAL}`,
                    color: TEAL,
                  }}
                >
                  Min / Max
                </th>
              </tr>
            </thead>
            <tbody>
              {properties.map((row) => (
                <tr key={row.id} style={{ borderTop: `1px solid ${BORDER}` }}>
                  <td
                    style={{
                      padding: "8px 12px",
                      fontSize: "0.8125rem",
                      color: TEXT,
                      fontWeight: 500,
                      borderRight: `1px solid ${BORDER}`,
                      position: 'relative',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {editingProperty === row.id ? (
                        <input
                          type="text"
                          value={row.feature}
                          onChange={(e) => updateProperty(row.id, { feature: e.target.value })}
                          onBlur={() => setEditingProperty(null)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') setEditingProperty(null);
                            if (e.key === 'Escape') setEditingProperty(null);
                          }}
                          autoFocus
                          style={{
                            width: '100%',
                            border: '1px solid #E5E7EB',
                            borderRadius: 4,
                            padding: '4px 8px',
                            fontSize: '0.8125rem',
                            fontFamily: 'inherit',
                          }}
                        />
                      ) : (
                        <>
                          <span onClick={() => setEditingProperty(row.id)} style={{ cursor: 'pointer', flex: 1 }}>
                            {row.feature}
                          </span>
                          {row.unit && (
                            <span style={{ color: "#9CA3AF", marginLeft: 4 }}>
                              ({row.unit})
                            </span>
                          )}
                          <div style={{ display: 'flex', gap: 4, marginLeft: 8 }}>
                            <button
                              onClick={() => setEditingProperty(row.id)}
                              style={{
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                                color: '#9CA3AF',
                                padding: 2,
                              }}
                              title="Edit property name"
                            >
                              <Edit2 size={14} />
                            </button>
                            <button
                              onClick={() => {
                                if (confirm(`Are you sure you want to delete "${row.feature}"?`)) {
                                  deleteProperty(row.id);
                                }
                              }}
                              style={{
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                                color: '#EF4444',
                                padding: 2,
                              }}
                              title="Delete property"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </td>
                  {(
                    [
                      { key: "basf" as const, fallback: row.basf },
                      { key: "syn" as const, fallback: row.syn },
                      { key: "tri" as const, fallback: row.tri },
                    ] as const
                  ).map(({ key, fallback }) => (
                    <td key={key} style={readOnlyCell}>
                      <input
                        type="text"
                        value={competitorValues[row.feature]?.[key] ?? fallback}
                        onChange={(e) =>
                          setCompetitorValues((prev) => ({
                            ...prev,
                            [row.feature]: {
                              basf: prev[row.feature]?.basf ?? row.basf,
                              syn: prev[row.feature]?.syn ?? row.syn,
                              tri: prev[row.feature]?.tri ?? row.tri,
                              [key]: e.target.value,
                            },
                          }))
                        }
                        style={editableInputStyle}
                      />
                    </td>
                  ))}
                  <td style={{ ...patentCell, borderRight: `1px solid ${BORDER}` }} />
                  <td
                    style={{
                      padding: "4px 8px",
                      background: "rgba(31,183,181,0.05)",
                      borderLeft: `2px solid ${TEAL}`,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        gap: 8,
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <input
                        type="text"
                        value={desired[row.feature]?.min || ""}
                        onChange={(e) =>
                          setDesired((prev) => ({
                            ...prev,
                            [row.feature]: {
                              ...prev[row.feature],
                              min: e.target.value,
                            },
                          }))
                        }
                        placeholder="Min"
                        style={{
                          width: 100,
                          border: "1px solid #E5E7EB",
                          borderRadius: 4,
                          padding: "6px 8px",
                          fontSize: "0.75rem",
                          textAlign: "center",
                        }}
                      />
                      <span style={{ color: "#9CA3AF", fontSize: "0.75rem" }}>
                        –
                      </span>
                      <input
                        type="text"
                        value={desired[row.feature]?.max || ""}
                        onChange={(e) =>
                          setDesired((prev) => ({
                            ...prev,
                            [row.feature]: {
                              ...prev[row.feature],
                              max: e.target.value,
                            },
                          }))
                        }
                        placeholder="Max"
                        style={{
                          width: 100,
                          border: "1px solid #E5E7EB",
                          borderRadius: 4,
                          padding: "6px 8px",
                          fontSize: "0.75rem",
                          textAlign: "center",
                        }}
                      />
                    </div>
                  </td>
                </tr>
              ))}
              {showAddProperty && (
                <tr style={{ borderTop: `1px solid ${BORDER}`, background: "rgba(31,183,181,0.03)" }}>
                  <td
                    style={{
                      padding: "8px 12px",
                      borderRight: `1px solid ${BORDER}`,
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <input
                        type="text"
                        placeholder="Property Name"
                        value={newProperty.feature}
                        onChange={(e) => setNewProperty(prev => ({ ...prev, feature: e.target.value }))}
                        style={{
                          width: '100%',
                          border: '1px solid #E5E7EB',
                          borderRadius: 4,
                          padding: '6px 8px',
                          fontSize: '0.8125rem',
                          fontFamily: 'inherit',
                        }}
                      />
                      <div style={{ display: 'flex', gap: 8 }}>
                        <input
                          type="text"
                          placeholder="Unit"
                          value={newProperty.unit}
                          onChange={(e) => setNewProperty(prev => ({ ...prev, unit: e.target.value }))}
                          style={{
                            flex: 1,
                            border: '1px solid #E5E7EB',
                            borderRadius: 4,
                            padding: '6px 8px',
                            fontSize: '0.8125rem',
                            fontFamily: 'inherit',
                          }}
                        />
                        <select
                          value={newProperty.dataType}
                          onChange={(e) => setNewProperty(prev => ({ ...prev, dataType: e.target.value as 'number' | 'text' | 'boolean' }))}
                          style={{
                            flex: 1,
                            border: '1px solid #E5E7EB',
                            borderRadius: 4,
                            padding: '6px 8px',
                            fontSize: '0.8125rem',
                            fontFamily: 'inherit',
                          }}
                        >
                          <option value="number">Number</option>
                          <option value="text">Text</option>
                          <option value="boolean">Boolean</option>
                        </select>
                      </div>
                    </div>
                  </td>
                  {['basf', 'syn', 'tri'].map(() => (
                    <td key={Math.random()} style={readOnlyCell}>
                      <input
                        type="text"
                        placeholder=""
                        disabled
                        style={{
                          ...editableInputStyle,
                          background: '#F9FAFB',
                          cursor: 'not-allowed',
                        }}
                      />
                    </td>
                  ))}
                  <td style={{ ...patentCell, borderRight: `1px solid ${BORDER}` }} />
                  <td
                    style={{
                      padding: "4px 8px",
                      background: "rgba(31,183,181,0.05)",
                      borderLeft: `2px solid ${TEAL}`,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        gap: 8,
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <button
                        onClick={() => {
                          if (newProperty.feature.trim()) {
                            addProperty({
                              feature: newProperty.feature,
                              unit: newProperty.unit,
                              category: newProperty.category,
                              dataType: newProperty.dataType,
                              basf: '',
                              syn: '',
                              tri: '',
                            });
                            setNewProperty({ feature: '', unit: '', category: '', dataType: 'number' });
                            setShowAddProperty(false);
                          }
                        }}
                        style={{
                          background: TEAL,
                          color: 'white',
                          border: 'none',
                          borderRadius: 4,
                          padding: '6px 12px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        Save
                      </button>
                      <button
                        onClick={() => {
                          setShowAddProperty(false);
                          setNewProperty({ feature: '', unit: '', category: '', dataType: 'number' });
                        }}
                        style={{
                          background: '#E5E7EB',
                          color: '#374151',
                          border: 'none',
                          borderRadius: 4,
                          padding: '6px 12px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
            <tfoot>
              {!showAddProperty && (
                <tr>
                  <td
                    colSpan={6}
                    style={{
                      borderTop: `1px solid ${BORDER}`,
                      padding: '12px',
                      textAlign: 'center',
                    }}
                  >
                    <button
                      onClick={() => setShowAddProperty(true)}
                      style={{
                        background: 'rgba(31,183,181,0.1)',
                        color: TEAL,
                        border: `1px dashed ${TEAL}`,
                        borderRadius: 6,
                        padding: '8px 16px',
                        fontSize: '0.8125rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        margin: '0 auto',
                      }}
                    >
                      <Plus size={16} />
                      Add Property
                    </button>
                  </td>
                </tr>
              )}
              <tr>
                <td colSpan={4} style={{ borderTop: `1px solid ${BORDER}` }} />
                <td style={{ borderTop: `1px solid ${BORDER}`, borderRight: `1px solid ${BORDER}` }} />
                <td style={{ borderTop: `1px solid ${BORDER}` }} />
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* showPatentRecipes removed */}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginTop: 20,
        }}
      >
        <button
          onClick={onBack}
          style={{
            border: `1px solid ${BORDER}`,
            color: "#6B7280",
            background: "white",
            borderRadius: 7,
            padding: "9px 18px",
            fontSize: "0.875rem",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <ChevronLeft size={15} /> Back
        </button>
        <button
          onClick={handleRun}
          disabled={running}
          style={{
            background: running ? "#9CA3AF" : TEAL,
            color: "white",
            border: "none",
            borderRadius: 7,
            padding: "11px 22px",
            fontSize: "0.875rem",
            fontWeight: 700,
            cursor: running ? "not-allowed" : "pointer",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          {running ? (
            <>
              <Loader
                size={16}
                style={{ animation: "spin 1s linear infinite" }}
              />
              Generating recipes…
            </>
          ) : (
            <>
              <Sparkles size={16} /> Generate Polymerization Recipes
            </>
          )}
        </button>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>

      {showPatentReport && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
          <div style={{ backgroundColor: '#F7FAFC', borderRadius: 8, padding: '24px', maxWidth: '900px', width: '100%', maxHeight: '90vh', overflowY: 'auto', position: 'relative' }}>
            <button onClick={() => setShowPatentReport(false)} style={{ position: 'absolute', top: 16, right: 16, background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.5rem', lineHeight: 1 }}>&times;</button>
            <LowAcnPatentReportViewer />
          </div>
        </div>
      )}
    </div>
  );
}

export function Step2PolymerizationRecommendations({
  onBack,
  onContinue,
  selectedRecipeId,
  onSelectRecipe,
  recipes,
  onUpdateProperty,
  onAddProperty,
  onDeleteProperty,
  onResetRecipe,
}: {
  onBack: () => void;
  onContinue: () => void;
  selectedRecipeId: string;
  onSelectRecipe: (id: string) => void;
  recipes: EditableRecipe[];
  onUpdateProperty: (recipeId: string, propertyId: string, updates: Partial<RecipeProperty>) => void;
  onAddProperty: (recipeId: string, property: RecipeProperty) => void;
  onDeleteProperty: (recipeId: string, propertyId: string) => void;
  onResetRecipe: (recipeId: string) => void;
}) {
  return (
    <div>
      <div
        style={{
          background: "linear-gradient(135deg, #1F5FA8 0%, #1FB7B5 100%)",
          padding: "20px 28px",
          marginBottom: 24,
          borderRadius: 8,
        }}
      >
        <h2
          style={{
            color: "white",
            fontSize: "1.125rem",
            fontWeight: 700,
            margin: "0 0 4px",
          }}
        >
          Polymerization Recipe Recommendations
        </h2>
        <p
          style={{
            color: "rgba(255,255,255,0.75)",
            fontSize: "0.8125rem",
            margin: 0,
          }}
        >
          5 candidate polymerization recipes generated from patent research and
          target polymer specifications
        </p>
      </div>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 14,
          marginBottom: 24,
        }}
      >
        {recipes.map((recipe) => (
          <PolymerizationRecipeCard
            key={recipe.id}
            recipe={recipe}
            selected={selectedRecipeId === recipe.id}
            onSelect={() => onSelectRecipe(recipe.id)}
            onUpdateProperty={onUpdateProperty}
            onAddProperty={onAddProperty}
            onDeleteProperty={onDeleteProperty}
            onResetRecipe={onResetRecipe}
          />
        ))}
      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <button
          onClick={onBack}
          style={{
            border: `1px solid ${BORDER}`,
            color: "#6B7280",
            background: "white",
            borderRadius: 7,
            padding: "9px 18px",
            fontSize: "0.875rem",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <ChevronLeft size={15} /> Back
        </button>
        <button
          onClick={onContinue}
          disabled={!selectedRecipeId}
          style={{
            background: selectedRecipeId ? TEAL : "#D1D5DB",
            color: "white",
            border: "none",
            borderRadius: 7,
            padding: "11px 22px",
            fontSize: "0.875rem",
            fontWeight: 700,
            cursor: selectedRecipeId ? "pointer" : "not-allowed",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          Continue to Customer Trial Feedback
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}

export function Step3CustomerTrialFeedback({
  onBack,
  onOptimize,
  selectedRecipeName,
  transferredData,
}: {
  onBack: () => void;
  onOptimize: () => void;
  selectedRecipeName: string;
  transferredData?: TransferredSpecData | null;
}) {
  return (
    <CustomerFeedbackProvider initialProperties={CUSTOMER_FEEDBACK_PROPERTIES}>
      <Step3CustomerTrialFeedbackContent
        onBack={onBack}
        onOptimize={onOptimize}
        selectedRecipeName={selectedRecipeName}
        transferredData={transferredData}
      />
    </CustomerFeedbackProvider>
  );
}

function Step3CustomerTrialFeedbackContent({
  onBack,
  onOptimize,
  selectedRecipeName,
  transferredData,
}: {
  onBack: () => void;
  onOptimize: () => void;
  selectedRecipeName: string;
  transferredData?: TransferredSpecData | null;
}) {
  const {
    customerFeedbackProperties,
    addCustomerFeedbackProperty,
    updateCustomerFeedbackProperty,
    deleteCustomerFeedbackProperty
  } = useCustomerFeedbackProperties();
  const [optimizing, setOptimizing] = useState(false);
  const [measuredValues, setMeasuredValues] = useState<Record<string, string>>({});
  const [targetValues, setTargetValues] = useState<Record<string, string>>(CUSTOMER_FEEDBACK_TARGET_VALUES);
  const [customerNotes, setCustomerNotes] = useState(DEMO_CUSTOMER_NOTES);
  const [showAddProperty, setShowAddProperty] = useState(false);
  const [editingProperty, setEditingProperty] = useState<string | null>(null);
  const [newProperty, setNewProperty] = useState({
    feature: '',
    unit: '',
    category: '',
    dataType: 'number' as 'number' | 'text' | 'boolean',
  });

  const handleOptimize = () => {
    setOptimizing(true);
    setTimeout(() => {
      setOptimizing(false);
      onOptimize();
    }, 1500);
  };

  return (
    <div>
      <div style={{ ...card, padding: "20px", marginBottom: 20 }}>
        <h3
          style={{
            margin: "0 0 16px",
            color: TEXT,
            fontSize: "0.95rem",
            fontWeight: 700,
          }}
        >
          Customer Trial Feedback
        </h3>

        <div style={{ marginBottom: 20 }}>
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 700,
              color: BLUE,
              marginBottom: 8,
              textTransform: "uppercase",
            }}
          >
            Selected Recipe
          </div>
          <div
            style={{
              padding: "10px 12px",
              background: BG,
              border: `1px solid ${BORDER}`,
              borderRadius: 6,
              fontSize: "0.875rem",
              fontWeight: 600,
              color: TEXT,
            }}
          >
            {selectedRecipeName}
          </div>
        </div>

        <div style={{ marginBottom: 20 }}>
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 700,
              color: BLUE,
              marginBottom: 10,
              textTransform: "uppercase",
            }}
          >
            Customer Feedback
          </div>
          <textarea
            value={customerNotes}
            onChange={(e) => setCustomerNotes(e.target.value)}
            style={{
              width: "100%",
              padding: "12px",
              background: BG,
              border: `1px solid ${BORDER}`,
              borderRadius: 6,
              fontSize: "0.8125rem",
              color: TEXT,
              lineHeight: 1.7,
              fontFamily: "inherit",
              resize: "vertical",
              minHeight: "80px",
              outline: "none",
            }}
            placeholder="Enter customer feedback..."
          />
        </div>

        <div style={{ marginBottom: 20 }}>
          <div
            style={{
              fontSize: "0.75rem",
              fontWeight: 700,
              color: BLUE,
              marginBottom: 10,
              textTransform: "uppercase",
            }}
          >
            Measured Values
          </div>
          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                minWidth: 420,
              }}
            >
              <thead>
                <tr style={{ background: BG }}>
                  {["Property", "Target", "Actual"].map((col) => (
                    <th
                      key={col}
                      style={{
                        padding: "9px 12px",
                        textAlign: "left",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        color: BLUE,
                        border: `1px solid ${BORDER}`,
                      }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {customerFeedbackProperties.map((row) => {
                  return (
                    <tr key={row.id}>
                      <td
                        style={{
                          padding: "9px 12px",
                          fontSize: "0.8125rem",
                          border: `1px solid ${BORDER}`,
                          position: 'relative',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          {editingProperty === row.id ? (
                            <input
                              type="text"
                              value={row.feature}
                              onChange={(e) => updateCustomerFeedbackProperty(row.id, { feature: e.target.value })}
                              onBlur={() => setEditingProperty(null)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') setEditingProperty(null);
                                if (e.key === 'Escape') setEditingProperty(null);
                              }}
                              autoFocus
                              style={{
                                width: '100%',
                                border: '1px solid #E5E7EB',
                                borderRadius: 4,
                                padding: '4px 8px',
                                fontSize: '0.8125rem',
                                fontFamily: 'inherit',
                              }}
                            />
                          ) : (
                            <>
                              <span onClick={() => setEditingProperty(row.id)} style={{ cursor: 'pointer', flex: 1 }}>
                                {row.feature}
                              </span>
                              {row.unit && (
                                <span style={{ color: "#9CA3AF", marginLeft: 4 }}>
                                  ({row.unit})
                                </span>
                              )}
                              <div style={{ display: 'flex', gap: 4, marginLeft: 8 }}>
                                <button
                                  onClick={() => setEditingProperty(row.id)}
                                  style={{
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    color: '#9CA3AF',
                                    padding: 2,
                                  }}
                                  title="Edit property name"
                                >
                                  <Edit2 size={14} />
                                </button>
                                <button
                                  onClick={() => {
                                    if (confirm(`Are you sure you want to delete "${row.feature}"?`)) {
                                      deleteCustomerFeedbackProperty(row.id);
                                    }
                                  }}
                                  style={{
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    color: '#EF4444',
                                    padding: 2,
                                  }}
                                  title="Delete property"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      </td>
                      <td
                        style={{
                          padding: "9px 12px",
                          fontSize: "0.8125rem",
                          border: `1px solid ${BORDER}`,
                        }}
                      >
                        {row.dataType === 'boolean' ? (
                          <input
                            type="checkbox"
                            checked={targetValues[row.feature] === 'true'}
                            onChange={(e) =>
                              setTargetValues((prev) => ({
                                ...prev,
                                [row.feature]: e.target.checked ? 'true' : 'false',
                              }))
                            }
                            style={{ accentColor: BLUE }}
                          />
                        ) : (
                          <input
                            type={row.dataType === 'number' ? 'number' : 'text'}
                            value={targetValues[row.feature] || ""}
                            onChange={(e) =>
                              setTargetValues((prev) => ({
                                ...prev,
                                [row.feature]: e.target.value,
                              }))
                            }
                            placeholder={`Target ${row.unit ? `(${row.unit})` : ''}`}
                            style={{
                              width: '100%',
                              border: '1px solid #E5E7EB',
                              borderRadius: 4,
                              padding: '6px 8px',
                              fontSize: '0.8125rem',
                              fontFamily: 'inherit',
                              textAlign: 'right',
                            }}
                          />
                        )}
                      </td>
                      <td
                        style={{
                          padding: "9px 12px",
                          fontSize: "0.8125rem",
                          border: `1px solid ${BORDER}`,
                        }}
                      >
                        {row.dataType === 'boolean' ? (
                          <input
                            type="checkbox"
                            checked={measuredValues[row.feature] === 'true'}
                            onChange={(e) =>
                              setMeasuredValues((prev) => ({
                                ...prev,
                                [row.feature]: e.target.checked ? 'true' : 'false',
                              }))
                            }
                            style={{ accentColor: BLUE }}
                          />
                        ) : (
                          <input
                            type={row.dataType === 'number' ? 'number' : 'text'}
                            value={measuredValues[row.feature] || ""}
                            onChange={(e) =>
                              setMeasuredValues((prev) => ({
                                ...prev,
                                [row.feature]: e.target.value,
                              }))
                            }
                            placeholder={`Actual ${row.unit ? `(${row.unit})` : ''}`}
                            style={{
                              width: '100%',
                              border: '1px solid #E5E7EB',
                              borderRadius: 4,
                              padding: '6px 8px',
                              fontSize: '0.8125rem',
                              fontFamily: 'inherit',
                              textAlign: 'right',
                            }}
                          />
                        )}
                      </td>
                    </tr>
                  );
                })}
                {showAddProperty && (
                  <tr style={{ background: "rgba(31,183,181,0.03)" }}>
                    <td
                      style={{
                        padding: "8px 12px",
                        border: `1px solid ${BORDER}`,
                      }}
                    >
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        <input
                          type="text"
                          placeholder="Property Name"
                          value={newProperty.feature}
                          onChange={(e) => setNewProperty(prev => ({ ...prev, feature: e.target.value }))}
                          style={{
                            width: '100%',
                            border: '1px solid #E5E7EB',
                            borderRadius: 4,
                            padding: '6px 8px',
                            fontSize: '0.8125rem',
                            fontFamily: 'inherit',
                          }}
                        />
                        <div style={{ display: 'flex', gap: 8 }}>
                          <input
                            type="text"
                            placeholder="Unit"
                            value={newProperty.unit}
                            onChange={(e) => setNewProperty(prev => ({ ...prev, unit: e.target.value }))}
                            style={{
                              flex: 1,
                              border: '1px solid #E5E7EB',
                              borderRadius: 4,
                              padding: '6px 8px',
                              fontSize: '0.8125rem',
                              fontFamily: 'inherit',
                            }}
                          />
                          <select
                            value={newProperty.dataType}
                            onChange={(e) => setNewProperty(prev => ({ ...prev, dataType: e.target.value as 'number' | 'text' | 'boolean' }))}
                            style={{
                              flex: 1,
                              border: '1px solid #E5E7EB',
                              borderRadius: 4,
                              padding: '6px 8px',
                              fontSize: '0.8125rem',
                              fontFamily: 'inherit',
                            }}
                          >
                            <option value="number">Number</option>
                            <option value="text">Text</option>
                            <option value="boolean">Boolean</option>
                          </select>
                        </div>
                      </div>
                    </td>
                    <td
                      style={{
                        padding: "9px 12px",
                        border: `1px solid ${BORDER}`,
                        background: '#F9FAFB',
                      }}
                    >
                      -
                    </td>
                    <td
                      style={{
                        padding: "9px 12px",
                        border: `1px solid ${BORDER}`,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          gap: 8,
                          alignItems: "center",
                        }}
                      >
                        <button
                          onClick={() => {
                            if (newProperty.feature.trim()) {
                              addCustomerFeedbackProperty({
                                feature: newProperty.feature,
                                unit: newProperty.unit,
                                category: newProperty.category,
                                dataType: newProperty.dataType,
                                basf: '',
                                syn: '',
                                tri: '',
                              });
                              setNewProperty({ feature: '', unit: '', category: '', dataType: 'number' });
                              setShowAddProperty(false);
                            }
                          }}
                          style={{
                            background: TEAL,
                            color: 'white',
                            border: 'none',
                            borderRadius: 4,
                            padding: '6px 12px',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          Save
                        </button>
                        <button
                          onClick={() => {
                            setShowAddProperty(false);
                            setNewProperty({ feature: '', unit: '', category: '', dataType: 'number' });
                          }}
                          style={{
                            background: '#E5E7EB',
                            color: '#374151',
                            border: 'none',
                            borderRadius: 4,
                            padding: '6px 12px',
                            fontSize: '0.75rem',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
              <tfoot>
                {!showAddProperty && (
                  <tr>
                    <td
                      colSpan={3}
                      style={{
                        borderTop: `1px solid ${BORDER}`,
                        padding: '12px',
                        textAlign: 'center',
                      }}
                    >
                      <button
                        onClick={() => setShowAddProperty(true)}
                        style={{
                          background: 'rgba(31,183,181,0.1)',
                          color: TEAL,
                          border: `1px dashed ${TEAL}`,
                          borderRadius: 6,
                          padding: '8px 16px',
                          fontSize: '0.8125rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          margin: '0 auto',
                        }}
                      >
                        <Plus size={16} />
                        Add Property
                      </button>
                    </td>
                  </tr>
                )}
              </tfoot>
            </table>
          </div>
        </div>


      </div>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <button
          onClick={onBack}
          style={{
            border: `1px solid ${BORDER}`,
            color: "#6B7280",
            background: "white",
            borderRadius: 7,
            padding: "9px 18px",
            fontSize: "0.875rem",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <ChevronLeft size={15} /> Back
        </button>
        <button
          onClick={handleOptimize}
          disabled={optimizing}
          style={{
            background: optimizing ? "#9CA3AF" : TEAL,
            color: "white",
            border: "none",
            borderRadius: 7,
            padding: "11px 22px",
            fontSize: "0.875rem",
            fontWeight: 700,
            cursor: optimizing ? "not-allowed" : "pointer",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          {optimizing ? (
            <>
              <Loader
                size={16}
                style={{ animation: "spin 1s linear infinite" }}
              />
              Optimizing…
            </>
          ) : (
            <>
              <Sparkles size={16} /> Optimize Polymerization Recipe
            </>
          )}
        </button>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function OptimizedRecipeCard({ recipe }: { recipe: OptimizedRecipe }) {
  const [showRecipe, setShowRecipe] = useState(false);
  const baseRecipe = POLYMERIZATION_RECIPES.find((item) => item.id === "recipe-2");

  return (
    <div style={{ ...card, padding: "18px", marginBottom: 16 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 14,
        }}
      >
        <h4 style={{ margin: 0, color: BLUE, fontSize: "0.9375rem" }}>
          {recipe.name}
        </h4>
        <span
          style={{
            background: "rgba(31,183,181,0.12)",
            color: TEAL,
            fontWeight: 700,
            fontSize: "0.8125rem",
            padding: "3px 10px",
            borderRadius: 20,
          }}
        >
          Confidence: {recipe.confidence}%
        </span>
      </div>

      <div style={{ marginBottom: 14 }}>
        <div
          style={{
            fontSize: "0.75rem",
            fontWeight: 700,
            color: BLUE,
            marginBottom: 8,
          }}
        >
          Modified Parameters
        </div>
        <table
          style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem" }}
        >
          <thead>
            <tr style={{ background: BG }}>
              {["Parameter", "Previous", "Revised"].map((col) => (
                <th
                  key={col}
                  style={{
                    padding: "8px 10px",
                    textAlign: "left",
                    border: `1px solid ${BORDER}`,
                    color: BLUE,
                  }}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {recipe.changes.map((change) => (
              <tr key={change.parameter}>
                <td style={{ padding: "8px 10px", border: `1px solid ${BORDER}` }}>
                  {change.parameter}
                </td>
                <td style={{ padding: "8px 10px", border: `1px solid ${BORDER}` }}>
                  {change.previous}
                </td>
                <td
                  style={{
                    padding: "8px 10px",
                    border: `1px solid ${BORDER}`,
                    color: TEAL,
                    fontWeight: 600,
                  }}
                >
                  {change.revised}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ marginBottom: 14 }}>
        <div
          style={{
            fontSize: "0.75rem",
            fontWeight: 700,
            color: BLUE,
            marginBottom: 8,
          }}
        >
          Predicted Impact
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 8,
          }}
        >
          {recipe.impacts.map((impact) => (
            <div
              key={impact.label}
              style={{
                padding: "8px 10px",
                background: BG,
                border: `1px solid ${BORDER}`,
                borderRadius: 6,
                fontSize: "0.8125rem",
              }}
            >
              <strong>{impact.label}:</strong> {impact.value}
            </div>
          ))}
        </div>
      </div>

      <button
        onClick={() => setShowRecipe((v) => !v)}
        style={{
          background: BLUE,
          color: "white",
          border: "none",
          borderRadius: 6,
          padding: "8px 16px",
          fontSize: "0.8125rem",
          fontWeight: 600,
          cursor: "pointer",
        }}
      >
        {showRecipe ? "Hide Recipe" : "View Recipe"}
      </button>

      {showRecipe && baseRecipe && (
        <RecipeDetailTable
          title={`${recipe.name} - Optimized Polymerization Recipe`}
          steps={getPolymerizationRecipeSteps({
            ...baseRecipe,
            chainTransferAgent: recipe.changes.find(
              (change) => change.parameter === "Chain Transfer Agent",
            )?.revised ?? baseRecipe.chainTransferAgent,
            temperature:
              recipe.changes.find(
                (change) => change.parameter === "Polymerization Temp",
              )?.revised ?? baseRecipe.temperature,
            initiator:
              recipe.changes.find((change) => change.parameter === "Initiator")
                ?.revised ?? baseRecipe.initiator,
            bdAcnRatio:
              recipe.changes.find((change) => change.parameter === "BD/ACN Ratio")
                ?.revised ?? baseRecipe.bdAcnRatio,
            water:
              recipe.changes.find((change) => change.parameter === "Water")
                ?.revised ?? baseRecipe.water,
          })}
        />
      )}
    </div>
  );
}

export function Step4OptimizedRecipes({ onBack }: { onBack: () => void }) {
  return (
    <div>
      <div
        style={{
          background: "linear-gradient(135deg, #1F5FA8 0%, #1FB7B5 100%)",
          padding: "20px 28px",
          marginBottom: 24,
          borderRadius: 8,
        }}
      >
        <h2
          style={{
            color: "white",
            fontSize: "1.125rem",
            fontWeight: 700,
            margin: "0 0 4px",
          }}
        >
          Optimized Polymerization Recipes
        </h2>
        <p
          style={{
            color: "rgba(255,255,255,0.75)",
            fontSize: "0.8125rem",
            margin: 0,
          }}
        >
          Revised recipes generated from customer trial feedback for Recipe 2
        </p>
      </div>

      {OPTIMIZED_RECIPES.map((recipe) => (
        <OptimizedRecipeCard key={recipe.id} recipe={recipe} />
      ))}

      <div style={{ display: "flex", justifyContent: "flex-start" }}>
        <button
          onClick={onBack}
          style={{
            border: `1px solid ${BORDER}`,
            color: "#6B7280",
            background: "white",
            borderRadius: 7,
            padding: "9px 18px",
            fontSize: "0.875rem",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <ChevronLeft size={15} /> Back
        </button>
      </div>
    </div>
  );
}

export type { TransferredSpecData };
