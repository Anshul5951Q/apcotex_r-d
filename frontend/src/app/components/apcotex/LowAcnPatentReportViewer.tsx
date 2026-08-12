import React from 'react';
import { usePatentResearch } from "../../contexts/PatentResearchContext";

const TEXT = "#111827";
const BORDER = "#E5E7EB";
const LINK = "#2563EB";
const BG = "#F9FAFB";

const documentStyles = {
  maxWidth: 900,
  margin: "0 auto",
  background: "white",
  padding: "48px 64px",
  boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
  fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  fontSize: "11pt",
  lineHeight: 1.6,
  color: TEXT,
} as const;

export function LowAcnPatentReportViewer() {
  const { state } = usePatentResearch();

  const report = state.structuredReport;

  // Fallback to legacy HTML report if no structured report
  if (!report) {
    if (state.reportHtml) {
      return (
        <div style={documentStyles}>
          <div 
            dangerouslySetInnerHTML={{ __html: state.reportHtml }} 
            className="patent-report-content"
          />
          <style>{`
            .patent-report-content h1 { text-align: center; font-size: 20pt; margin-bottom: 24px; border-bottom: 2px solid ${TEXT}; padding-bottom: 24px; text-transform: uppercase; font-weight: 800; }
            .patent-report-content h2 { font-size: 16pt; margin-top: 32px; margin-bottom: 16px; font-weight: 700; text-transform: uppercase; color: #1F2937; }
            .patent-report-content h3 { font-size: 13pt; margin-top: 24px; margin-bottom: 12px; font-weight: 600; color: #374151; }
            .patent-report-content table { width: 100%; border-collapse: collapse; margin-top: 16px; margin-bottom: 16px; font-size: 10.5pt; }
            .patent-report-content th { border: 1px solid ${BORDER}; padding: 10px 12px; background: #F3F4F6; text-align: left; font-weight: 600; }
            .patent-report-content td { border: 1px solid ${BORDER}; padding: 10px 12px; vertical-align: top; }
            .patent-report-content a { color: ${LINK}; text-decoration: none; }
            .patent-report-content a:hover { text-decoration: underline; }
            .patent-report-content p { text-align: justify; margin-bottom: 16px; color: #374151; }
            .patent-report-content ul { padding-left: 24px; margin-bottom: 16px; color: #374151; }
            .patent-report-content li { margin-bottom: 6px; }
          `}</style>
        </div>
      );
    }
    return null;
  }

  return (
    <div style={documentStyles}>
      <header style={{ marginBottom: 40, textAlign: 'center' }}>
        <h1 style={{ fontSize: "22pt", fontWeight: 800, margin: "0 0 24px 0", borderBottom: `3px solid ${TEXT}`, paddingBottom: 24, textTransform: "uppercase", letterSpacing: "-0.025em" }}>
          {report.title || `${state.compoundName} - Patent Research Report`}
        </h1>
      </header>

      <section style={{ marginBottom: 40 }}>
        <h2 style={{ fontSize: "16pt", fontWeight: 700, margin: "0 0 16px 0", textTransform: "uppercase", color: "#111827", borderBottom: `2px solid ${BORDER}`, paddingBottom: 8 }}>
          1. Abstract
        </h2>
        <p style={{ margin: 0, textAlign: 'justify', color: '#374151' }}>{report.abstract}</p>
      </section>

      <section style={{ marginBottom: 40 }}>
        <h2 style={{ fontSize: "16pt", fontWeight: 700, margin: "0 0 24px 0", textTransform: "uppercase", color: "#111827", borderBottom: `2px solid ${BORDER}`, paddingBottom: 8 }}>
          2. Methodology
        </h2>

        {report.methodology_patents?.map((patent: any, idx: number) => {
          const details = patent.patent_details || {};
          const method = patent.polymerization_method || {};
          
          return (
            <div key={idx} style={{ marginBottom: 40 }}>
              <h3 style={{ fontSize: "14pt", fontWeight: 600, color: "#1F2937", margin: "0 0 16px 0", display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ background: '#E5E7EB', padding: '4px 12px', borderRadius: 4, fontSize: '11pt' }}>Patent {idx + 1}</span>
                {details.patent_title}
              </h3>

              {/* Details Grid */}
              <div style={{ background: BG, border: `1px solid ${BORDER}`, borderRadius: 8, padding: 20, marginBottom: 20 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px 24px' }}>
                  <div><strong style={{ color: '#4B5563' }}>Number:</strong> {details.patent_number}</div>
                  <div><strong style={{ color: '#4B5563' }}>Jurisdiction:</strong> {details.jurisdiction}</div>
                  <div><strong style={{ color: '#4B5563' }}>Assignee:</strong> {details.assignee}</div>
                  <div><strong style={{ color: '#4B5563' }}>Year:</strong> {details.publication_year}</div>
                  <div style={{ gridColumn: '1 / -1' }}><strong style={{ color: '#4B5563' }}>Polymer Type:</strong> {details.polymer_type}</div>
                  <div style={{ gridColumn: '1 / -1' }}><strong style={{ color: '#4B5563' }}>Relevance:</strong> {details.relevance_to_target}</div>
                </div>
              </div>

              {/* Polymerization Method Table */}
              <h4 style={{ fontSize: "12pt", fontWeight: 600, margin: "0 0 12px 0", color: '#374151' }}>Polymerization / Synthesis Method</h4>
              <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 24, fontSize: '10.5pt' }}>
                <tbody>
                  {Object.entries(method).map(([key, value]) => {
                    if (!value || value === 'Not disclosed' || value === 'Not explicitly disclosed') return null;
                    const formattedKey = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                    return (
                      <tr key={key}>
                        <td style={{ border: `1px solid ${BORDER}`, padding: '8px 12px', background: '#F9FAFB', fontWeight: 600, width: '35%', color: '#4B5563' }}>
                          {formattedKey}
                        </td>
                        <td style={{ border: `1px solid ${BORDER}`, padding: '8px 12px', color: '#111827' }}>
                          {String(value)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {/* Experimental Evidence */}
              {patent.experimental_evidence && patent.experimental_evidence.length > 0 && (
                <div style={{ marginBottom: 24 }}>
                  <h4 style={{ fontSize: "12pt", fontWeight: 600, margin: "0 0 12px 0", color: '#374151' }}>Relevant Experimental Evidence</h4>
                  <ul style={{ margin: 0, paddingLeft: 24, color: '#374151' }}>
                    {patent.experimental_evidence.map((ev: string, i: number) => (
                      <li key={i} style={{ marginBottom: 6 }}>{ev}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Technical Relevance */}
              {patent.technical_relevance && (
                <div>
                  <h4 style={{ fontSize: "12pt", fontWeight: 600, margin: "0 0 8px 0", color: '#374151' }}>Technical Relevance</h4>
                  <p style={{ margin: 0, color: '#4B5563', fontStyle: 'italic' }}>{patent.technical_relevance}</p>
                </div>
              )}
            </div>
          );
        })}
      </section>

      <section style={{ marginBottom: 40 }}>
        <h2 style={{ fontSize: "16pt", fontWeight: 700, margin: "0 0 16px 0", textTransform: "uppercase", color: "#111827", borderBottom: `2px solid ${BORDER}`, paddingBottom: 8 }}>
          3. Cross-Patent Comparison & Trends
        </h2>
        <ul style={{ margin: 0, paddingLeft: 24, color: '#374151' }}>
          {report.cross_patent_comparison?.map((point: string, idx: number) => (
            <li key={idx} style={{ marginBottom: 8 }}>{point}</li>
          ))}
        </ul>
      </section>

      <section>
        <h2 style={{ fontSize: "16pt", fontWeight: 700, margin: "0 0 16px 0", textTransform: "uppercase", color: "#111827", borderBottom: `2px solid ${BORDER}`, paddingBottom: 8 }}>
          4. References
        </h2>
        <ul style={{ margin: 0, paddingLeft: 24, color: '#374151' }}>
          {report.references?.map((ref: string, idx: number) => (
            <li key={idx} style={{ marginBottom: 8, wordBreak: 'break-word' }}>{ref}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
