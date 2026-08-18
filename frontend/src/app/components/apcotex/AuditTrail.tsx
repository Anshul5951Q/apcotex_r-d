import { useState, useEffect } from "react";
import { Search, Filter, Download, Eye } from "lucide-react";
import { getAuditLogs, type AuditLogEntry } from "../../services/auditApi";

const BLUE = "#1F5FA8";
const TEAL = "#1FB7B5";
const BORDER = "#E5E7EB";

export function AuditTrail() {
  const [searchTerm, setSearchTerm] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [auditData, setAuditData] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAuditLogs();
  }, []);

  const loadAuditLogs = async () => {
    try {
      setLoading(true);
      const response = await getAuditLogs({ page_size: 100 });
      setAuditData(response.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit logs");
      console.error("Error loading audit logs:", err);
    } finally {
      setLoading(false);
    }
  };

  const getActionType = (action: string): string => {
    if (action.includes("LOGIN") || action.includes("LOGOUT")) return "auth";
    if (action.includes("CREATED")) return "create";
    if (action.includes("UPDATED")) return "update";
    if (action.includes("DELETED")) return "delete";
    if (action.includes("VIEWED")) return "view";
    if (action.includes("EXPORTED") || action.includes("DOWNLOADED")) return "export";
    return "other";
  };

  const formatDetail = (detail: Record<string, any>): string => {
    if (!detail || Object.keys(detail).length === 0) return "No details";
    const keys = Object.keys(detail);
    if (keys.includes("username")) return `User: ${detail.username}`;
    if (keys.includes("compound")) return `Compound: ${detail.compound}`;
    if (keys.includes("recipe_name")) return `Recipe: ${detail.recipe_name}`;
    if (keys.includes("property")) return `Property: ${detail.property}`;
    if (keys.includes("error")) return `Error: ${detail.error}`;
    return JSON.stringify(detail).substring(0, 100);
  };

  const formatTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp);
    return date.toLocaleString("en-US", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  const filteredData = auditData.filter((item) => {
    const detailStr = formatDetail(item.detail);
    const actionType = getActionType(item.action);
    const matchesSearch =
      item.user_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
      detailStr.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filterType === "all" || actionType === filterType;
    return matchesSearch && matchesFilter;
  });

  const getActionColor = (type: string) => {
    switch (type) {
      case "create":
        return "#10B981";
      case "update":
        return "#F59E0B";
      case "delete":
        return "#EF4444";
      case "auth":
        return "#6366F1";
      case "view":
        return "#3B82F6";
      case "export":
        return "#8B5CF6";
      case "other":
        return "#6B7280";
      default:
        return "#6B7280";
    }
  };

  return (
    <div style={{ padding: "24px", minHeight: "100%" }}>
      <div style={{ maxWidth: "1400px", margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: "32px" }}>
          <h1
            style={{
              fontSize: "1.875rem",
              fontWeight: 700,
              color: "#1F2937",
              marginBottom: "8px",
            }}
          >
            Audit Trail
          </h1>
          <p style={{ color: "#6B7280", fontSize: "0.875rem" }}>
            Track all user activities and system events
          </p>
        </div>

        {/* Filters */}
        <div
          style={{
            display: "flex",
            gap: "16px",
            marginBottom: "24px",
            flexWrap: "wrap",
          }}
        >
          {/* Search */}
          <div style={{ position: "relative", flex: 1, minWidth: 280 }}>
            <Search
              size={18}
              style={{
                position: "absolute",
                left: "12px",
                top: "50%",
                transform: "translateY(-50%)",
                color: "#9CA3AF",
              }}
            />
            <input
              type="text"
              placeholder="Search by user, action, or details..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                width: "100%",
                padding: "10px 12px 10px 40px",
                border: `1px solid ${BORDER}`,
                borderRadius: "8px",
                fontSize: "0.875rem",
                outline: "none",
              }}
            />
          </div>

          {/* Filter Dropdown */}
          <div style={{ position: "relative" }}>
            <Filter
              size={18}
              style={{
                position: "absolute",
                left: "12px",
                top: "50%",
                transform: "translateY(-50%)",
                color: "#9CA3AF",
              }}
            />
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              style={{
                padding: "10px 12px 10px 40px",
                border: `1px solid ${BORDER}`,
                borderRadius: "8px",
                fontSize: "0.875rem",
                outline: "none",
                cursor: "pointer",
                minWidth: 160,
              }}
            >
              <option value="all">All Actions</option>
              <option value="create">Create</option>
              <option value="update">Update</option>
              <option value="delete">Delete</option>
              <option value="view">View</option>
              <option value="auth">Authentication</option>
              <option value="export">Export</option>
            </select>
          </div>

          {/* Export Button */}
          <button
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 20px",
              background: BLUE,
              color: "white",
              border: "none",
              borderRadius: "8px",
              fontSize: "0.875rem",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            <Download size={16} />
            Export
          </button>
        </div>

        {/* Audit Trail Table */}
        <div
          style={{
            background: "white",
            border: `1px solid ${BORDER}`,
            borderRadius: "12px",
            overflow: "hidden",
          }}
        >
          {/* Loading State */}
          {loading && (
            <div
              style={{
                padding: "48px",
                textAlign: "center",
                color: "#6B7280",
              }}
            >
              Loading audit logs...
            </div>
          )}

          {/* Error State */}
          {!loading && error && (
            <div
              style={{
                padding: "48px",
                textAlign: "center",
                color: "#EF4444",
              }}
            >
              {error}
            </div>
          )}

          {/* Table */}
          {!loading && !error && (
            <>
              {/* Table Header */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "80px 150px 180px 1fr 200px 80px",
                  padding: "16px 20px",
                  background: "#F9FAFB",
                  borderBottom: `1px solid ${BORDER}`,
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: "#6B7280",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                <div>ID</div>
                <div>User</div>
                <div>Action</div>
                <div>Details</div>
                <div>Timestamp</div>
                <div></div>
              </div>

              {/* Table Body */}
              {filteredData.map((item) => {
                const actionType = getActionType(item.action);
                return (
                  <div
                    key={item.id}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "80px 150px 180px 1fr 200px 80px",
                      padding: "16px 20px",
                      borderBottom: `1px solid ${BORDER}`,
                      fontSize: "0.875rem",
                      alignItems: "center",
                    }}
                  >
                    <div style={{ color: "#6B7280" }}>#{item.id.substring(0, 8)}</div>
                    <div style={{ fontWeight: 500, color: "#1F2937" }}>{item.user_id}</div>
                    <div>
                      <span
                        style={{
                          display: "inline-block",
                          padding: "4px 10px",
                          borderRadius: "4px",
                          fontSize: "0.75rem",
                          fontWeight: 500,
                          background: `${getActionColor(actionType)}15`,
                          color: getActionColor(actionType),
                        }}
                      >
                        {item.action}
                      </span>
                    </div>
                    <div style={{ color: "#4B5563" }}>{formatDetail(item.detail)}</div>
                    <div style={{ color: "#6B7280", fontSize: "0.8125rem" }}>
                      {formatTimestamp(item.created_at)}
                    </div>
                    <div>
                      <button
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          padding: "6px",
                          background: "transparent",
                          border: `1px solid ${BORDER}`,
                          borderRadius: "6px",
                          cursor: "pointer",
                        }}
                      >
                        <Eye size={14} style={{ color: "#6B7280" }} />
                      </button>
                    </div>
                  </div>
                );
              })}

              {filteredData.length === 0 && (
                <div
                  style={{
                    padding: "48px",
                    textAlign: "center",
                    color: "#6B7280",
                  }}
                >
                  No audit trail records found
                </div>
              )}
            </>
          )}
        </div>

        {/* Summary Stats */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "16px",
            marginTop: "24px",
          }}
        >
          <div
            style={{
              background: "white",
              border: `1px solid ${BORDER}`,
              borderRadius: "8px",
              padding: "20px",
            }}
          >
            <div style={{ fontSize: "0.75rem", color: "#6B7280", marginBottom: "8px" }}>
              Total Records
            </div>
            <div style={{ fontSize: "1.875rem", fontWeight: 700, color: "#1F2937" }}>
              {auditData.length}
            </div>
          </div>
          <div
            style={{
              background: "white",
              border: `1px solid ${BORDER}`,
              borderRadius: "8px",
              padding: "20px",
            }}
          >
            <div style={{ fontSize: "0.75rem", color: "#6B7280", marginBottom: "8px" }}>
              Today's Activity
            </div>
            <div style={{ fontSize: "1.875rem", fontWeight: 700, color: TEAL }}>
              {auditData.filter((item) => {
                const today = new Date().toISOString().split('T')[0];
                return item.created_at.startsWith(today);
              }).length}
            </div>
          </div>
          <div
            style={{
              background: "white",
              border: `1px solid ${BORDER}`,
              borderRadius: "8px",
              padding: "20px",
            }}
          >
            <div style={{ fontSize: "0.75rem", color: "#6B7280", marginBottom: "8px" }}>
              Active Users
            </div>
            <div style={{ fontSize: "1.875rem", fontWeight: 700, color: BLUE }}>
              {new Set(auditData.map(item => item.user_id)).size}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
