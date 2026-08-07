import { useState, useEffect } from "react";
import { X, FileText, Download, Loader } from "lucide-react";
import { getResearchRuns, downloadFile } from "../../services/researchApi";

const BLUE = "#1F5FA8";
const TEXT = "#1F2937";
const BORDER = "#E5E7EB";
const BG = "#F7FAFC";
const GREEN = "#10B981";
const RED = "#EF4444";
const GRAY = "#6B7280";

export function PreviousReports({ onClose }: { onClose: () => void }) {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchReports() {
      try {
        const data = await getResearchRuns();
        setReports(data.items || []);
      } catch (err: any) {
        setError(err.message || "Failed to load reports");
      } finally {
        setLoading(false);
      }
    }
    fetchReports();
  }, []);

  const handleDownload = async (id: string, format: "pdf" | "docx", name: string) => {
    try {
      await downloadFile(id, format, `APCOTEX_Report_${name}.${format}`);
    } catch (err) {
      alert("Failed to download file.");
    }
  };

  const getStatusColor = (status: string) => {
    if (status === "COMPLETED") return GREEN;
    if (status === "FAILED") return RED;
    if (status === "CANCELLED") return GRAY;
    return BLUE;
  };

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: "rgba(0,0,0,0.4)", zIndex: 9999,
      display: "flex", justifyContent: "center", alignItems: "center"
    }}>
      <div style={{
        background: "white", width: "90%", maxWidth: 1000, maxHeight: "85vh",
        borderRadius: 12, display: "flex", flexDirection: "column",
        boxShadow: "0 10px 25px -5px rgba(0,0,0,0.1)"
      }}>
        <div style={{ padding: "20px 24px", borderBottom: `1px solid ${BORDER}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: "1.25rem", color: BLUE, display: "flex", alignItems: "center", gap: 10 }}>
            <FileText size={20} /> Previous Reports
          </h2>
          <button onClick={onClose} style={{ background: "transparent", border: "none", cursor: "pointer", color: "#9CA3AF" }}>
            <X size={24} />
          </button>
        </div>

        <div style={{ padding: 24, overflowY: "auto", flex: 1 }}>
          {loading ? (
            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 200, color: BLUE }}>
              <Loader style={{ animation: "spin 1s linear infinite" }} size={30} />
            </div>
          ) : error ? (
            <div style={{ color: RED, textAlign: "center", padding: 40 }}>{error}</div>
          ) : reports.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: GRAY }}>
              <p>No patent reports have been generated yet.</p>
              <p>Generate your first research report to see it here.</p>
              <button onClick={onClose} style={{
                marginTop: 15, background: BLUE, color: "white", padding: "8px 16px",
                border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 600
              }}>Start New Research</button>
            </div>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
              <thead>
                <tr style={{ borderBottom: `2px solid ${BORDER}`, textAlign: "left", color: GRAY }}>
                  <th style={{ padding: "12px 16px", fontWeight: 600 }}>Compound</th>
                  <th style={{ padding: "12px 16px", fontWeight: 600 }}>Created On</th>
                  <th style={{ padding: "12px 16px", fontWeight: 600 }}>Jurisdictions</th>
                  <th style={{ padding: "12px 16px", fontWeight: 600 }}>Status</th>
                  <th style={{ padding: "12px 16px", fontWeight: 600, textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {reports.map(r => (
                  <tr key={r.id} style={{ borderBottom: `1px solid ${BORDER}`, color: TEXT }}>
                    <td style={{ padding: "16px", fontWeight: 500 }}>{r.compound_name}</td>
                    <td style={{ padding: "16px" }}>{new Date(r.created_at).toLocaleString()}</td>
                    <td style={{ padding: "16px" }}>
                      {r.jurisdictions?.join(", ") || "N/A"}
                    </td>
                    <td style={{ padding: "16px" }}>
                      <span style={{
                        display: "inline-block", padding: "4px 8px", borderRadius: 20,
                        fontSize: "0.75rem", fontWeight: 600,
                        background: `${getStatusColor(r.status)}20`,
                        color: getStatusColor(r.status)
                      }}>
                        {r.status}
                      </span>
                    </td>
                    <td style={{ padding: "16px", textAlign: "right" }}>
                      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                        {r.status === "COMPLETED" ? (
                          <>
                            <button onClick={() => handleDownload(r.id, "pdf", r.compound_name)} title="Download PDF" style={{
                              background: "white", border: `1px solid ${BORDER}`, padding: 6, borderRadius: 6, cursor: "pointer", color: TEXT
                            }}><Download size={16} /></button>
                            <button onClick={() => handleDownload(r.id, "docx", r.compound_name)} title="Download DOCX" style={{
                              background: "white", border: `1px solid ${BORDER}`, padding: 6, borderRadius: 6, cursor: "pointer", color: BLUE
                            }}><Download size={16} /></button>
                          </>
                        ) : (
                          <span style={{ color: GRAY, fontSize: "0.8125rem" }}>No files</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
