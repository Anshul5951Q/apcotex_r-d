import { usePatentResearch } from "../../contexts/PatentResearchContext";

const TEXT = "#1a1a1a";
const BORDER = "#333333";
const LINK = "#1F5FA8";

const documentStyles = {
  maxWidth: 816,
  margin: "0 auto",
  background: "white",
  padding: "48px 56px",
  boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
  fontFamily: '"Times New Roman", Times, serif',
  fontSize: "12pt",
  lineHeight: 1.5,
  color: TEXT,
} as const;

export function LowAcnPatentReportViewer() {
  const { state } = usePatentResearch();

  if (!state.reportHtml) {
    return null;
  }

  return (
    <div style={documentStyles}>
      <div 
        dangerouslySetInnerHTML={{ __html: state.reportHtml }} 
        style={{
          // Apply some basic styling for markdown tables
          // The rest of the styling comes from the markdown structure itself
        }}
        className="patent-report-content"
      />
      <style>{`
        .patent-report-content h1 { text-align: center; font-size: 18pt; margin-bottom: 24px; border-bottom: 2px solid ${TEXT}; padding-bottom: 24px; text-transform: uppercase; }
        .patent-report-content h2 { font-size: 14pt; margin-top: 28px; margin-bottom: 12px; font-weight: 700; text-transform: uppercase; }
        .patent-report-content h3 { font-size: 12pt; margin-top: 20px; margin-bottom: 10px; font-weight: 700; }
        .patent-report-content table { width: 100%; border-collapse: collapse; margin-top: 16px; margin-bottom: 16px; font-size: 10pt; }
        .patent-report-content th { border: 1px solid ${BORDER}; padding: 8px 10px; background: #f5f5f5; text-align: left; }
        .patent-report-content td { border: 1px solid ${BORDER}; padding: 8px 10px; vertical-align: top; }
        .patent-report-content a { color: ${LINK}; word-break: break-all; }
        .patent-report-content p { text-align: justify; margin-bottom: 16px; }
        .patent-report-content ul { padding-left: 22px; margin-bottom: 16px; }
        .patent-report-content li { margin-bottom: 4px; }
      `}</style>
    </div>
  );
}
