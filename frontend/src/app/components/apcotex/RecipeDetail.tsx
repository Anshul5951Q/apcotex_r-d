import { useState } from "react";
import {
  ChevronLeft,
  CheckCircle2,
  Clock,
  User,
  AlertCircle,
  FlaskConical,
} from "lucide-react";
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";

const C = {
  blue: "#1F5FA8",
  teal: "#1FB7B5",
  red: "#D93A2F",
  text: "#1F2937",
  textMuted: "#6B7280",
  textLight: "#9CA3AF",
  border: "#E5E7EB",
  bg: "#F7FAFC",
  bgCard: "#FFFFFF",
  blueTint: "rgba(31,95,168,0.07)",
  tealTint: "rgba(31,183,181,0.08)",
  redTint: "rgba(217,58,47,0.08)",
};

const card = {
  background: C.bgCard,
  border: `1px solid ${C.border}`,
  borderRadius: 10,
  boxShadow:
    "0 1px 4px rgba(31,95,168,0.07), 0 0 0 0.5px rgba(31,95,168,0.04)",
};

const RECIPE_DATA = {
  "ZEN-02-New": {
    id: "ZEN-02-New",
    score: 94,
    confidence: 91,
    description:
      "High-tensile NBR grade optimised for bonding applications. Two-stage temp ramp protocol with anionic surfactant system.",
  },
  "APX-TG-441": {
    id: "APX-TG-441",
    score: 89,
    confidence: 87,
    description:
      "Balanced Tg/tensile formulation suitable for low-temperature applications. KPS initiator at optimised dosing.",
  },
  "BR-HighTemp-07": {
    id: "BR-HighTemp-07",
    score: 82,
    confidence: 79,
    description:
      "High-temperature resistant NBR recipe with elevated Temp Max performance above 90°C.",
  },
};

const PR_ROWS = Array.from({ length: 15 }, (_, i) => ({
  id: `PR#${String(i + 1).padStart(2, "0")}`,
  pH: (6.9 + Math.random() * 0.9).toFixed(1),
  water: (48 + Math.random() * 6).toFixed(1) + "%",
  temp: Math.round(78 + Math.random() * 15) + "°C",
  ingreds: [
    i % 3 === 0 ? "Yes" : i % 3 === 1 ? "No" : "X",
    i % 4 === 0 ? "Yes" : "No",
    i % 2 === 0 ? "Yes" : "X",
    i % 5 === 0 ? "X" : "Yes",
    i % 3 === 1 ? "Yes" : "No",
    i % 4 === 2 ? "X" : "Yes",
    i % 2 === 1 ? "No" : "Yes",
    i % 6 === 0 ? "X" : "Yes",
  ],
}));

const RADAR_DATA = [
  {
    subject: "Tensile",
    recipe: 96,
    target: 100,
    competitor: 87,
  },
  {
    subject: "Elongation",
    recipe: 99,
    target: 100,
    competitor: 92,
  },
  {
    subject: "Temp Max",
    recipe: 93,
    target: 95,
    competitor: 78,
  },
  {
    subject: "Viscosity",
    recipe: 88,
    target: 90,
    competitor: 75,
  },
  {
    subject: "Bond Str.",
    recipe: 95,
    target: 100,
    competitor: 82,
  },
  { subject: "pH", recipe: 97, target: 95, competitor: 90 },
];

const PROCESS_PARAMS = [
  { param: "Reactor Type", value: "Jacketed CSTR, 500L" },
  { param: "Stage 1 Temperature", value: "60°C ± 1°C" },
  { param: "Stage 2 Temperature", value: "75°C ± 1°C" },
  { param: "Transition Point (Conversion)", value: "65%" },
  { param: "Agitation Speed", value: "120 RPM" },
  {
    param: "Nitrogen Blanket",
    value: "Yes — throughout polymerisation",
  },
  { param: "Target Conversion", value: "≥ 92%" },
  {
    param: "Shortstop Agent",
    value: "Diethylhydroxylamine (DEHA), 0.1%",
  },
  { param: "Stripping Temp", value: "65°C, vacuum 80 mbar" },
  {
    param: "Final pH Adjustment",
    value: "KOH solution to 7.2 ± 0.1",
  },
  { param: "Filtration", value: "100 μm mesh, inline" },
  { param: "Estimated Batch Time", value: "6.5 – 7.5 hours" },
];

const HISTORY_EVENTS = [
  {
    date: "Apr 20, 2026",
    label: "Sent to lab for trial",
    user: "R. Sharma",
    type: "action",
  },
  {
    date: "Apr 18, 2026",
    label:
      "Step 4 lab comparison complete — 87% model accuracy confirmed",
    user: "System",
    type: "milestone",
  },
  {
    date: "Apr 15, 2026",
    label: "AI Prediction run — model version v2.4.1",
    user: "System",
    type: "ai",
  },
  {
    date: "Apr 12, 2026",
    label:
      "Target specification defined (10 properties, 10 importance weights)",
    user: "R. Sharma",
    type: "action",
  },
  {
    date: "Apr 10, 2026",
    label:
      "Competitor data uploaded (BASF, Synthomer, Trinseo)",
    user: "M. Patel",
    type: "action",
  },
  {
    date: "Apr 08, 2026",
    label: "Project APX-NBR-2024-Q1 created",
    user: "R. Sharma",
    type: "milestone",
  },
];

const PREDICTIONS = [
  {
    label: "Tensile Strength",
    pred: "26.8 MPa",
    target: "25–28 MPa",
    ok: true,
  },
  {
    label: "Elongation at Break",
    pred: "572%",
    target: "550–600%",
    ok: true,
  },
  {
    label: "Temp Max",
    pred: "88°C",
    target: "85–95°C",
    ok: true,
  },
  {
    label: "Viscosity",
    pred: "1310 cP",
    target: "1100–1400 cP",
    ok: true,
  },
  { label: "pH", pred: "7.2", target: "7.0–7.5", ok: true },
  {
    label: "Bond Strength",
    pred: "4.5 N/mm",
    target: "4.0–5.0 N/mm",
    ok: true,
  },
];

function IngredChip({ val }: { val: string }) {
  const map: Record<string, { bg: string; color: string }> = {
    Yes: { bg: "rgba(31,183,181,0.10)", color: "#0d9e9c" },
    No: { bg: "#F3F4F6", color: C.textMuted },
    X: { bg: C.blueTint, color: C.blue },
  };
  const s = map[val] || map.No;

  return (
    <span
      style={{
        background: s.bg,
        color: s.color,
        fontSize: "0.6875rem",
        padding: "3px 9px",
        borderRadius: 5,
        fontWeight: 700,
      }}
    >
      {val}
    </span>
  );
}

export function RecipeDetail({
  recipeId: propRecipeId,
  onBack,
}: {
  recipeId?: string;
  onBack?: () => void;
}) {
  const recipeId = propRecipeId || "ZEN-02-New";
  const [activeTab, setActiveTab] = useState("composition");

  const recipe = RECIPE_DATA[
    recipeId as keyof typeof RECIPE_DATA
  ] || {
    id: recipeId || "Unknown",
    score: 82,
    confidence: 79,
    description: "AI-generated formulation candidate.",
  };

  const tabs = [
    { id: "composition", label: "Composition" },
    { id: "properties", label: "Predicted Properties" },
    { id: "process", label: "Process Parameters" },
    { id: "history", label: "History" },
  ];

  return (
    <div
      style={{
        padding: "28px 32px 56px",
        background: C.bg,
        minHeight: "100vh",
      }}
    >
      <button
        onClick={onBack || (() => window.history.back())}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          color: C.textMuted,
          background: "none",
          border: "none",
          cursor: "pointer",
          fontSize: "0.875rem",
          marginBottom: 22,
          padding: "6px 0",
          fontWeight: 500,
        }}
      >
        <ChevronLeft size={16} /> Back to Recipe Simulator
      </button>

      <div
        style={{
          ...card,
          padding: "22px 26px",
          marginBottom: 24,
          borderTop: `3px solid ${C.blue}`,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 24,
          }}
        >
          <div style={{ flex: 1 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                marginBottom: 8,
                flexWrap: "wrap",
              }}
            >
              <div
                style={{
                  width: 40,
                  height: 40,
                  borderRadius: 10,
                  background: C.blueTint,
                  border: `1px solid rgba(31,95,168,0.15)`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <FlaskConical
                  size={20}
                  color={C.blue}
                  strokeWidth={1.5}
                />
              </div>

              <h1
                style={{
                  color: C.blue,
                  fontSize: "1.375rem",
                  fontWeight: 800,
                  letterSpacing: "-0.02em",
                  lineHeight: 1,
                }}
              >
                {recipe.id}
              </h1>

              <div
                style={{
                  background: C.tealTint,
                  borderRadius: 20,
                  padding: "4px 14px",
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                }}
              >
                <span
                  style={{
                    color: C.teal,
                    fontWeight: 800,
                    fontSize: "1rem",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {recipe.score}%
                </span>
                <span
                  style={{
                    color: C.teal,
                    fontSize: "0.75rem",
                    fontWeight: 500,
                  }}
                >
                  match
                </span>
              </div>

              <div
                style={{
                  background: C.blueTint,
                  borderRadius: 20,
                  padding: "4px 12px",
                }}
              >
                <span
                  style={{
                    color: C.blue,
                    fontSize: "0.8125rem",
                    fontWeight: 600,
                  }}
                >
                  Confidence: {recipe.confidence}%
                </span>
              </div>
            </div>

            <p
              style={{
                color: C.textMuted,
                fontSize: "0.875rem",
                lineHeight: 1.65,
                maxWidth: 580,
              }}
            >
              {recipe.description}
            </p>
          </div>

          <div
            style={{ display: "flex", gap: 10, flexShrink: 0 }}
          >
            <button
              style={{
                border: `1.5px solid ${C.red}`,
                color: C.red,
                background: "white",
                borderRadius: 7,
                padding: "9px 18px",
                fontSize: "0.875rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Reject Recipe
            </button>
            <button
              style={{
                background: C.teal,
                color: "white",
                border: "none",
                borderRadius: 7,
                padding: "9px 20px",
                fontSize: "0.875rem",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Approve for Trial
            </button>
          </div>
        </div>
      </div>

      <div
        style={{
          display: "flex",
          borderBottom: `2px solid ${C.border}`,
          marginBottom: 24,
          gap: 0,
          background: "white",
          borderRadius: "8px 8px 0 0",
          padding: "0 4px",
          border: `1px solid ${C.border}`,
          boxShadow: "0 1px 3px rgba(31,95,168,0.05)",
        }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "13px 22px",
              background: "none",
              border: "none",
              borderBottom:
                activeTab === tab.id
                  ? `2.5px solid ${C.blue}`
                  : "2.5px solid transparent",
              marginBottom: -2,
              color:
                activeTab === tab.id ? C.blue : C.textMuted,
              fontWeight: activeTab === tab.id ? 700 : 500,
              fontSize: "0.875rem",
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "composition" && (
        <div style={{ ...card, overflow: "hidden" }}>
          <div
            style={{
              padding: "13px 18px",
              borderBottom: `1px solid ${C.border}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span
              style={{
                fontSize: "0.875rem",
                fontWeight: 600,
                color: C.text,
              }}
            >
              Ingredient Matrix · PR#01–PR#15
            </span>

            <div style={{ display: "flex", gap: 10 }}>
              {[
                {
                  val: "Yes",
                  bg: "rgba(31,183,181,0.10)",
                  color: "#0d9e9c",
                },
                {
                  val: "No",
                  bg: "#F3F4F6",
                  color: C.textMuted,
                },
                { val: "X", bg: C.blueTint, color: C.blue },
              ].map((c) => (
                <span
                  key={c.val}
                  style={{
                    background: c.bg,
                    color: c.color,
                    fontSize: "0.6875rem",
                    padding: "2px 9px",
                    borderRadius: 5,
                    fontWeight: 700,
                  }}
                >
                  {c.val}
                </span>
              ))}
              <span
                style={{
                  fontSize: "0.75rem",
                  color: C.textLight,
                  marginLeft: 4,
                }}
              >
                = Included · Excluded · Conditional
              </span>
            </div>
          </div>

          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                borderCollapse: "collapse",
                minWidth: 800,
                width: "100%",
              }}
            >
              <thead>
                <tr style={{ background: C.bg }}>
                  {[
                    "Recipe",
                    "pH",
                    "Water Qty",
                    "Temp",
                    "Monomer A",
                    "Monomer B",
                    "Surfactant",
                    "Initiator",
                    "CTA",
                    "Buffer",
                    "DEHA",
                    "HEC",
                  ].map((h, i) => (
                    <th
                      key={h}
                      style={{
                        padding: "9px 13px",
                        textAlign: i === 0 ? "left" : "center",
                        fontSize: "0.75rem",
                        fontWeight: 700,
                        color: C.blue,
                        borderBottom: `1.5px solid ${C.border}`,
                        borderRight: `1px solid ${C.border}`,
                        whiteSpace: "nowrap",
                        minWidth: i === 0 ? 70 : 80,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {PR_ROWS.map((row, i) => (
                  <tr
                    key={row.id}
                    style={{
                      borderTop: `1px solid ${C.border}`,
                      background:
                        i % 2 === 0
                          ? "white"
                          : "rgba(247,250,252,0.5)",
                    }}
                  >
                    <td
                      style={{
                        padding: "8px 13px",
                        fontSize: "0.875rem",
                        color: C.blue,
                        fontWeight: 700,
                        borderRight: `1px solid ${C.border}`,
                      }}
                    >
                      {row.id}
                    </td>

                    {[row.pH, row.water, row.temp].map(
                      (v, j) => (
                        <td
                          key={j}
                          style={{
                            padding: "8px 13px",
                            fontSize: "0.8125rem",
                            color: C.text,
                            textAlign: "center",
                            borderRight: `1px solid ${C.border}`,
                            fontVariantNumeric: "tabular-nums",
                          }}
                        >
                          {v}
                        </td>
                      ),
                    )}

                    {row.ingreds.map((val, j) => (
                      <td
                        key={j}
                        style={{
                          padding: "8px 13px",
                          textAlign: "center",
                          borderRight: `1px solid ${C.border}`,
                        }}
                      >
                        <IngredChip val={val} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === "properties" && (
        <div
          style={{
            display: "flex",
            gap: 20,
            alignItems: "flex-start",
          }}
        >
          <div style={{ ...card, padding: "24px", flex: 1 }}>
            <h3
              style={{
                color: C.text,
                fontSize: "0.9375rem",
                fontWeight: 700,
                marginBottom: 6,
              }}
            >
              Property Comparison
            </h3>
            <p
              style={{
                color: C.textMuted,
                fontSize: "0.8125rem",
                marginBottom: 20,
              }}
            >
              Radar overlay: This Recipe vs. Desired Target vs.
              Nearest Competitor
            </p>

            <div style={{ width: "100%", height: 360 }}>
              <ResponsiveContainer>
                <RadarChart data={RADAR_DATA}>
                  <PolarGrid stroke="#D1D5DB" />
                  <PolarAngleAxis
                    dataKey="subject"
                    tick={{ fill: "#6B7280", fontSize: 12 }}
                  />
                  <Radar
                    name="This Recipe"
                    dataKey="recipe"
                    stroke={C.teal}
                    fill={C.teal}
                    fillOpacity={0.18}
                  />
                  <Radar
                    name="Target"
                    dataKey="target"
                    stroke={C.blue}
                    fill={C.blue}
                    fillOpacity={0.08}
                  />
                  <Radar
                    name="Competitor"
                    dataKey="competitor"
                    stroke={C.red}
                    fill={C.red}
                    fillOpacity={0.05}
                  />
                  <Legend />
                  <Tooltip />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div
            style={{
              width: 330,
              flexShrink: 0,
              display: "flex",
              flexDirection: "column",
              gap: 16,
            }}
          >
            <div style={{ ...card, padding: "18px" }}>
              <h3
                style={{
                  color: C.text,
                  fontSize: "0.875rem",
                  fontWeight: 700,
                  marginBottom: 14,
                }}
              >
                Predicted Properties
              </h3>

              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 10,
                }}
              >
                {PREDICTIONS.map((item) => (
                  <div
                    key={item.label}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      justifyContent: "space-between",
                      gap: 12,
                      paddingBottom: 10,
                      borderBottom: `1px solid ${C.border}`,
                    }}
                  >
                    <div>
                      <div
                        style={{
                          color: C.text,
                          fontSize: "0.8125rem",
                          fontWeight: 600,
                          marginBottom: 2,
                        }}
                      >
                        {item.label}
                      </div>
                      <div
                        style={{
                          color: C.textLight,
                          fontSize: "0.75rem",
                        }}
                      >
                        Target: {item.target}
                      </div>
                    </div>

                    <div style={{ textAlign: "right" }}>
                      <div
                        style={{
                          color: C.blue,
                          fontSize: "0.8125rem",
                          fontWeight: 700,
                        }}
                      >
                        {item.pred}
                      </div>
                      <div
                        style={{
                          color: item.ok ? "#0d9e9c" : C.red,
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        {item.ok ? (
                          <CheckCircle2 size={12} />
                        ) : (
                          <AlertCircle size={12} />
                        )}
                        {item.ok
                          ? "Within target"
                          : "Needs review"}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ ...card, padding: "18px" }}>
              <h3
                style={{
                  color: C.text,
                  fontSize: "0.875rem",
                  fontWeight: 700,
                  marginBottom: 10,
                }}
              >
                Review Notes
              </h3>
              <div
                style={{
                  background: C.redTint,
                  color: C.red,
                  borderRadius: 8,
                  padding: "10px 12px",
                  fontSize: "0.8125rem",
                  fontWeight: 500,
                }}
              >
                Competitor comparison shows this candidate is
                strongest on bond strength and tensile balance.
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "process" && (
        <div style={{ ...card, overflow: "hidden" }}>
          <div
            style={{
              padding: "14px 20px",
              borderBottom: `1px solid ${C.border}`,
              fontSize: "0.9375rem",
              fontWeight: 700,
              color: C.text,
            }}
          >
            Suggested Process Parameters
          </div>

          <div style={{ padding: "8px 0" }}>
            {PROCESS_PARAMS.map((row, i) => (
              <div
                key={row.param}
                style={{
                  display: "grid",
                  gridTemplateColumns: "280px 1fr",
                  gap: 16,
                  padding: "12px 20px",
                  borderTop:
                    i > 0 ? `1px solid ${C.border}` : undefined,
                }}
              >
                <div
                  style={{
                    fontSize: "0.8125rem",
                    color: C.textMuted,
                    fontWeight: 600,
                  }}
                >
                  {row.param}
                </div>
                <div
                  style={{
                    fontSize: "0.8125rem",
                    color: C.text,
                  }}
                >
                  {row.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "history" && (
        <div style={{ ...card, padding: "18px 20px" }}>
          <h3
            style={{
              color: C.text,
              fontSize: "0.9375rem",
              fontWeight: 700,
              marginBottom: 16,
            }}
          >
            Activity History
          </h3>

          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}
          >
            {HISTORY_EVENTS.map((event, idx) => {
              const meta =
                event.type === "milestone"
                  ? {
                      icon: <CheckCircle2 size={15} />,
                      color: "#0d9e9c",
                      bg: "rgba(31,183,181,0.10)",
                    }
                  : event.type === "ai"
                    ? {
                        icon: <Clock size={15} />,
                        color: C.blue,
                        bg: C.blueTint,
                      }
                    : {
                        icon: <User size={15} />,
                        color: C.red,
                        bg: C.redTint,
                      };

              return (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    gap: 12,
                    alignItems: "flex-start",
                    paddingBottom: 14,
                    borderBottom:
                      idx < HISTORY_EVENTS.length - 1
                        ? `1px solid ${C.border}`
                        : "none",
                  }}
                >
                  <div
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: "50%",
                      background: meta.bg,
                      color: meta.color,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    {meta.icon}
                  </div>

                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        color: C.text,
                        fontSize: "0.8125rem",
                        fontWeight: 600,
                        marginBottom: 2,
                      }}
                    >
                      {event.label}
                    </div>
                    <div
                      style={{
                        color: C.textLight,
                        fontSize: "0.75rem",
                      }}
                    >
                      {event.date} · {event.user}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}