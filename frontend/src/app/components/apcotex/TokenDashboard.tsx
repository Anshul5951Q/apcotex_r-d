import { useState, useEffect } from "react";
import { Activity, Server, Zap, Search, ChevronDown, DollarSign, AlertTriangle } from "lucide-react";
import { adminUsageApi, UsageSummary, ProviderUsage, StageUsage, PaginatedRuns, DetailedRunUsage } from "../../services/adminUsageApi";

const BLUE = "#1F5FA8";
const TEAL = "#1FB7B5";
const RED = "#D93A2F";
const BORDER = "#E5E7EB";

export function TokenDashboard() {
  const [viewMode, setViewMode] = useState<"period" | "run">("period");
  const [timeFilter, setTimeFilter] = useState("today"); // default to today
  
  // Period Mode State
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [providers, setProviders] = useState<ProviderUsage[]>([]);
  const [stages, setStages] = useState<StageUsage[]>([]);
  
  // Run Mode State
  const [recentRuns, setRecentRuns] = useState<PaginatedRuns | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string>("");
  const [runDetail, setRunDetail] = useState<DetailedRunUsage | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (viewMode === "period") {
      loadPeriodData();
    } else {
      loadRunData();
    }
  }, [viewMode, timeFilter]);

  useEffect(() => {
    if (viewMode === "run" && selectedRunId) {
      loadRunDetail(selectedRunId);
    }
  }, [selectedRunId]);

  const loadPeriodData = async () => {
    try {
      setLoading(true);
      setError(null);
      const results = await Promise.allSettled([
        adminUsageApi.getSummary(timeFilter),
        adminUsageApi.getByProvider(timeFilter),
        adminUsageApi.getByStage(timeFilter)
      ]);
      
      if (results[0].status === 'fulfilled') setSummary(results[0].value);
      if (results[1].status === 'fulfilled') setProviders(results[1].value);
      if (results[2].status === 'fulfilled') setStages(results[2].value);
      
      if (results.every(r => r.status === 'rejected')) {
        setError("Failed to load period data.");
      }
    } catch (err) {
      setError("Failed to load usage data");
    } finally {
      setLoading(false);
    }
  };

  const loadRunData = async () => {
    try {
      setLoading(true);
      setError(null);
      const runs = await adminUsageApi.getByRun(timeFilter, 1, 50);
      setRecentRuns(runs);
      if (runs.items.length > 0 && !selectedRunId) {
        setSelectedRunId(runs.items[0].run_id);
      } else if (runs.items.length === 0) {
        setRunDetail(null);
        setSelectedRunId("");
      }
    } catch (err) {
      setError("Failed to load recent runs.");
    } finally {
      setLoading(false);
    }
  };

  const loadRunDetail = async (runId: string) => {
    try {
      setLoading(true);
      const detail = await adminUsageApi.getRunDetail(runId);
      setRunDetail(detail);
    } catch (err) {
      setError("Failed to load run details.");
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (num: number | null | undefined) => {
    if (num == null) return "-";
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
  };

  const formatCurrency = (num: number) => {
    return '$' + num.toFixed(4);
  };

  const handleResetToday = async () => {
    if (window.confirm("Reset today's usage view? Historical usage will not be deleted.")) {
      try {
        await adminUsageApi.resetToday();
        alert("Today's usage metrics have been reset.");
        if (viewMode === "period") loadPeriodData();
        else loadRunData();
      } catch (err) {
        alert("Failed to reset today's usage.");
      }
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#F7FAFC" }}>
      {/* Header */}
      <div style={{ padding: "32px 40px", background: "white", borderBottom: `1px solid ${BORDER}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "#111827", margin: 0 }}>
            Token & API Usage
          </h1>
          <p style={{ color: "#6B7280", margin: "4px 0 0 0", fontSize: "0.875rem" }}>
            Monitor system-wide LLM token consumption and API costs.
          </p>
        </div>
        
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <div style={{ display: "flex", background: "#F3F4F6", padding: 4, borderRadius: 8 }}>
            <button
              onClick={() => setViewMode("period")}
              style={{
                padding: "6px 16px", borderRadius: 6, fontSize: "0.875rem", fontWeight: 500,
                background: viewMode === "period" ? "white" : "transparent",
                color: viewMode === "period" ? "#111827" : "#6B7280",
                boxShadow: viewMode === "period" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
                border: "none", cursor: "pointer", outline: "none"
              }}
            >
              Period Usage
            </button>
            <button
              onClick={() => setViewMode("run")}
              style={{
                padding: "6px 16px", borderRadius: 6, fontSize: "0.875rem", fontWeight: 500,
                background: viewMode === "run" ? "white" : "transparent",
                color: viewMode === "run" ? "#111827" : "#6B7280",
                boxShadow: viewMode === "run" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
                border: "none", cursor: "pointer", outline: "none"
              }}
            >
              Current Research Run
            </button>
          </div>

          <div style={{ width: 1, height: 24, background: BORDER, margin: "0 8px" }} />

          {timeFilter === "today" && (
            <button
              onClick={handleResetToday}
              style={{
                padding: "8px 16px", borderRadius: 6, border: `1px solid ${BORDER}`, background: "white",
                fontSize: "0.875rem", fontWeight: 500, color: RED, cursor: "pointer", outline: "none"
              }}
            >
              Reset Today
            </button>
          )}
          <select 
            value={timeFilter}
            onChange={(e) => setTimeFilter(e.target.value)}
            style={{
              padding: "8px 32px 8px 16px", borderRadius: 6, border: `1px solid ${BORDER}`, background: "white",
              fontSize: "0.875rem", color: "#374151", cursor: "pointer", outline: "none"
            }}
          >
            <option value="today">Today</option>
            <option value="7d">Last 7 Days</option>
            <option value="28d">Last 28 Days</option>
            <option value="this_month">This Month</option>
            <option value="last_month">Last Month</option>
          </select>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ padding: "32px 40px", flex: 1, overflowY: "auto" }}>
        {error && (
          <div style={{ padding: 20, background: "#FEF2F2", color: RED, borderRadius: 8, border: `1px solid #FCA5A5`, marginBottom: 24 }}>
            {error}
          </div>
        )}

        {viewMode === "run" && (
          <div style={{ marginBottom: 24, display: "flex", gap: 16, alignItems: "center" }}>
            <span style={{ fontWeight: 500, color: "#374151" }}>Select Run:</span>
            <select
              value={selectedRunId}
              onChange={(e) => setSelectedRunId(e.target.value)}
              style={{
                padding: "8px 16px", borderRadius: 6, border: `1px solid ${BORDER}`, background: "white",
                fontSize: "0.875rem", color: "#111827", cursor: "pointer", outline: "none", minWidth: 300
              }}
            >
              <option value="" disabled>-- Select a run --</option>
              {recentRuns?.items.map(r => (
                <option key={r.run_id} value={r.run_id}>
                  {r.compound_name} ({new Date(r.created_at).toLocaleString()}) - {r.status}
                </option>
              ))}
            </select>
          </div>
        )}

        {viewMode === "run" && runDetail?.architecture_violation && (
          <div style={{ padding: 16, background: "#FEF2F2", color: RED, borderRadius: 8, border: `1px solid #FCA5A5`, marginBottom: 24, display: "flex", alignItems: "center", gap: 12 }}>
            <AlertTriangle size={24} />
            <div>
              <div style={{ fontWeight: 600 }}>Architecture Violation</div>
              <div style={{ fontSize: "0.875rem" }}>{runDetail.architecture_violation}</div>
            </div>
          </div>
        )}

        {loading && !summary && !runDetail ? (
          <div style={{ textAlign: "center", padding: 60, color: "#6B7280" }}>Loading dashboard data...</div>
        ) : (
          <>
            {/* Top Stats */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 20, marginBottom: 32 }}>
              <div style={{ background: "white", padding: 24, borderRadius: 12, border: `1px solid ${BORDER}`, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                  <div style={{ background: "rgba(31,95,168,0.1)", padding: 10, borderRadius: 8, color: BLUE }}>
                    <Activity size={20} />
                  </div>
                  <span style={{ fontSize: "0.875rem", fontWeight: 500, color: "#6B7280" }}>Total Tokens</span>
                </div>
                <div style={{ fontSize: "2rem", fontWeight: 700, color: "#111827" }}>
                  {formatNumber(viewMode === "period" ? summary?.llm_total_tokens : runDetail?.total?.total_tokens)}
                </div>
              </div>

              <div style={{ background: "white", padding: 24, borderRadius: 12, border: `1px solid ${BORDER}`, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                  <div style={{ background: "rgba(31,183,181,0.1)", padding: 10, borderRadius: 8, color: TEAL }}>
                    <Server size={20} />
                  </div>
                  <span style={{ fontSize: "0.875rem", fontWeight: 500, color: "#6B7280" }}>LLM Calls</span>
                </div>
                <div style={{ fontSize: "2rem", fontWeight: 700, color: "#111827" }}>
                  {formatNumber(viewMode === "period" ? summary?.llm_calls : runDetail?.total?.llm_calls)}
                </div>
              </div>

              <div style={{ background: "white", padding: 24, borderRadius: 12, border: `1px solid ${BORDER}`, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                  <div style={{ background: "rgba(217,58,47,0.1)", padding: 10, borderRadius: 8, color: RED }}>
                    <Zap size={20} />
                  </div>
                  <span style={{ fontSize: "0.875rem", fontWeight: 500, color: "#6B7280" }}>Serper Requests</span>
                </div>
                <div style={{ fontSize: "2rem", fontWeight: 700, color: "#111827" }}>
                  {formatNumber(viewMode === "period" ? summary?.serper_requests : runDetail?.total?.serper_requests)}
                </div>
              </div>

              <div style={{ background: "white", padding: 24, borderRadius: 12, border: `1px solid ${BORDER}`, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                  <div style={{ background: "rgba(16,185,129,0.1)", padding: 10, borderRadius: 8, color: "#10B981" }}>
                    <DollarSign size={20} />
                  </div>
                  <span style={{ fontSize: "0.875rem", fontWeight: 500, color: "#6B7280" }}>Estimated Cost</span>
                </div>
                <div style={{ fontSize: "2rem", fontWeight: 700, color: "#111827" }}>
                  {formatCurrency(viewMode === "period" ? (summary?.estimated_cost || 0) : (runDetail?.total?.cost || 0))}
                </div>
              </div>
            </div>

            {/* Tables Grid */}
            <div style={{ display: "grid", gridTemplateColumns: viewMode === "period" ? "1fr 2fr" : "1fr", gap: 24 }}>
              
              {/* Providers Table - Only in Period Mode */}
              {viewMode === "period" && (
                <div style={{ background: "white", borderRadius: 12, border: `1px solid ${BORDER}`, overflow: "hidden", display: "flex", flexDirection: "column" }}>
                  <div style={{ padding: "16px 24px", borderBottom: `1px solid ${BORDER}`, background: "#F9FAFB" }}>
                    <h3 style={{ margin: 0, fontSize: "0.9375rem", fontWeight: 600 }}>By Provider</h3>
                  </div>
                  <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                    <thead>
                      <tr style={{ borderBottom: `1px solid ${BORDER}`, color: "#6B7280", fontSize: "0.75rem", textTransform: "uppercase" }}>
                        <th style={{ padding: "12px 24px", fontWeight: 500 }}>Provider</th>
                        <th style={{ padding: "12px 24px", fontWeight: 500 }}>Logical Calls</th>
                        <th style={{ padding: "12px 24px", fontWeight: 500 }}>Attempts (S/F)</th>
                        <th style={{ padding: "12px 24px", fontWeight: 500 }}>Tokens</th>
                        <th style={{ padding: "12px 24px", fontWeight: 500 }}>Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {providers.map(p => (
                        <tr key={p.provider} style={{ borderBottom: `1px solid ${BORDER}` }}>
                          <td style={{ padding: "12px 24px", fontSize: "0.875rem", fontWeight: 500, color: "#111827", textTransform: "capitalize" }}>
                            {p.provider}
                          </td>
                          <td style={{ padding: "12px 24px", fontSize: "0.875rem", color: "#6B7280" }}>
                            {formatNumber(p.logical_calls)}
                          </td>
                          <td style={{ padding: "12px 24px", fontSize: "0.875rem", color: "#6B7280" }}>
                            {p.provider_attempts} ({p.successful_attempts}/{p.failed_attempts})
                          </td>
                          <td style={{ padding: "12px 24px", fontSize: "0.875rem", color: "#6B7280" }}>
                            {formatNumber((p.input_tokens || 0) + (p.output_tokens || 0))}
                          </td>
                          <td style={{ padding: "12px 24px", fontSize: "0.875rem", color: "#6B7280" }}>
                            {formatCurrency(p.cost)}
                          </td>
                        </tr>
                      ))}
                      {providers.length === 0 && (
                        <tr>
                          <td colSpan={5} style={{ padding: "24px", textAlign: "center", color: "#6B7280", fontSize: "0.875rem" }}>No data</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Stages Table */}
              <div style={{ background: "white", borderRadius: 12, border: `1px solid ${BORDER}`, overflow: "hidden", display: "flex", flexDirection: "column" }}>
                <div style={{ padding: "16px 24px", borderBottom: `1px solid ${BORDER}`, background: "#F9FAFB" }}>
                  <h3 style={{ margin: 0, fontSize: "0.9375rem", fontWeight: 600 }}>By Stage</h3>
                </div>
                <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${BORDER}`, color: "#6B7280", fontSize: "0.75rem", textTransform: "uppercase" }}>
                      <th style={{ padding: "12px 24px", fontWeight: 500 }}>Stage</th>
                      <th style={{ padding: "12px 24px", fontWeight: 500 }}>Logical LLM</th>
                      <th style={{ padding: "12px 24px", fontWeight: 500 }}>Attempts (S/F)</th>
                      <th style={{ padding: "12px 24px", fontWeight: 500 }}>Serper Reqs</th>
                      <th style={{ padding: "12px 24px", fontWeight: 500 }}>Tokens</th>
                      <th style={{ padding: "12px 24px", fontWeight: 500 }}>Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(viewMode === "period" ? stages : (runDetail?.stages || [])).map((s, idx) => (
                      <tr key={s.stage || idx} style={{ borderBottom: `1px solid ${BORDER}` }}>
                        <td style={{ padding: "12px 24px", fontSize: "0.875rem", fontWeight: 500, color: "#111827", textTransform: "capitalize" }}>
                          {s.stage?.replace(/_/g, ' ')}
                        </td>
                        <td style={{ padding: "12px 24px", fontSize: "0.875rem", color: "#6B7280" }}>
                          {formatNumber(s.logical_llm_calls)}
                        </td>
                        <td style={{ padding: "12px 24px", fontSize: "0.875rem", color: s.failed_attempts > 0 ? RED : "#6B7280", fontWeight: s.failed_attempts > 0 ? 600 : 400 }}>
                          {s.provider_attempts} ({s.successful_attempts}/{s.failed_attempts})
                        </td>
                        <td style={{ padding: "12px 24px", fontSize: "0.875rem", color: "#6B7280" }}>
                          {formatNumber(s.serper_requests)}
                        </td>
                        <td style={{ padding: "12px 24px", fontSize: "0.875rem", color: "#6B7280" }}>
                          {formatNumber(s.total_tokens)}
                        </td>
                        <td style={{ padding: "12px 24px", fontSize: "0.875rem", color: "#6B7280" }}>
                          {formatCurrency(s.cost)}
                        </td>
                      </tr>
                    ))}
                    {(viewMode === "period" ? stages : (runDetail?.stages || [])).length === 0 && (
                      <tr>
                        <td colSpan={6} style={{ padding: "24px", textAlign: "center", color: "#6B7280", fontSize: "0.875rem" }}>No data</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

            </div>
          </>
        )}
      </div>
    </div>
  );
}
