import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import jsPDF from "jspdf";

import {
  ArrowLeft,
  Briefcase,
  CalendarClock,
  ListOrdered,
  Download,
  Loader2,
  User,
  TrendingUp,
  Award,
  Target,
  AlertCircle,
  Star,
  ThumbsUp,
  ThumbsDown,
  FileText,
} from "lucide-react";
import PoweredByIScale from "@/components/PoweredByIScale";

const API_BASE_URL = `${(import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "")}/api`;
const formatMarkdown = (text: string): string => {
  return text
    .replace(/##\s*/g, "\n\n## ")        
    .replace(/\n\-\s*/g, "\n\n- ")        
    .replace(/Strengths:/gi, "\n\n### Strengths\n")
    .replace(/Areas for Improvement/gi, "\n\n### Areas for Improvement\n")
    .replace(/Communication:/gi, "\n\n### Communication\n")
    .replace(/Technical Knowledge/gi, "\n\n### Technical Knowledge\n")
    .replace(/Problem-Solving/gi, "\n\n### Problem-Solving\n")
    .replace(/\n{3,}/g, "\n\n")         
    .trim();
};
interface InterviewResult {
  score: number;
  feedback: string;
  areasForImprovement: string[];
  name?: string;
  email?: string;
  role?: string;
  tabSwitches?: number;
  faceLostCount?: number;
  faceLostSeconds?: number;
  multipleFacesCount?: number;
  movementEvents?: number;
}

export default function Results({
  sessionId,
  onBack,
  name,
  email,
  photo,
  role,
  totalQuestions,
}: {
  sessionId: string;
  onBack: () => void;
  name: string;
  email: string;
  photo: string | null;
  role: string;
  totalQuestions: number;
}) {
  const [result, setResult] = useState<InterviewResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const markdownToPlainText = (markdown: string): string => {
    return markdown
      .replace(/^#+\s*/gm, "")  // remove all headers
      .replace(/\*\*/g, "")     // bold
      .replace(/\*/g, "")       // italic
      .replace(/-\s/g, "• ")    // bullets
      .trim();
  };

  useEffect(() => {
    const fetchResult = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/log/${sessionId}`);
        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || `Error ${response.status}: Unable to fetch results`);
        }

        const data = await response.json();
        const areasForImprovement = parseAreasForImprovement(data.feedback);

        setResult({
          score: data.score || 0,
          feedback: data.feedback || "",
          areasForImprovement,
          name: data.name || "",
          email: data.email || "",
          role: data.role || "",
          tabSwitches: data.tab_switches || 0,
          faceLostCount: data.face_lost_count || 0,
          faceLostSeconds: data.face_lost_seconds || 0,
          multipleFacesCount: data.multiple_faces_count || 0,
          movementEvents: data.movement_events || 0,
        });
      } catch (err: any) {
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchResult();
  }, [sessionId]);

  const parseAreasForImprovement = (feedback: string): string[] => {
    const lines = feedback.split("\n");
    const improvements: string[] = [];

    let capture = false;

    for (const line of lines) {
      if (line.trim().toLowerCase().startsWith("## areas for improvement")) {
        capture = true;
        continue;
      }

      if (capture && line.trim().startsWith("##")) {
        break;
      }

      if (capture && line.trim().startsWith("-")) {
        improvements.push(line.replace("-", "").trim());
      }
    }

    return improvements;
  };

  const getScoreColor = (score: number) => {
    if (score >= 8) return "text-acc-emerald";
    if (score >= 6) return "text-acc-copper";
    return "text-[#D92B32]";
  };

  const getScoreBgColor = (score: number) => {
    if (score >= 8) return "bg-[rgba(95,164,127,.08)] border-[rgba(95,164,127,.3)]";
    if (score >= 6) return "bg-[rgba(201,154,114,.08)] border-[rgba(201,154,114,.3)]";
    return "bg-[rgba(217,43,50,.12)] border-[rgba(217,43,50,.3)]";
  };

  const getScoreLabel = (score: number) => {
    if (score >= 9) return "Outstanding";
    if (score >= 8) return "Excellent";
    if (score >= 7) return "Good";
    if (score >= 6) return "Average";
    if (score >= 5) return "Below Average";
    return "Needs Improvement";
  };
  const markdownToStyledLines = (markdown: string): { text: string, bold: boolean }[] => {
    const lines = markdown.split("\n");
    const styled: { text: string; bold: boolean }[] = [];

    lines.forEach((line) => {
      let clean = line
        .replace(/\*\*/g, "")
        .replace(/\*/g, "")
        .trim();

      if (line.startsWith("##")) {
        styled.push({ text: clean.replace(/^##\s*/, ""), bold: true });
      } else if (line.startsWith("- ") || line.startsWith("* ")) {
        styled.push({ text: "• " + clean.replace(/^[-*]\s*/, ""), bold: false });
      } else if (clean.length > 0) {
        styled.push({ text: clean, bold: false });
      }
    });

    return styled;
  };


  // Props are empty when this page is opened via URL/session ID; fall back to
  // the candidate details returned by the backend for this session.
  const displayName = name || result?.name || "Candidate";
  const displayEmail = email || result?.email || "";
  const displayRole = role || result?.role || "";

 const downloadPDF = () => {
  if (!result) return;

  const pdf = new jsPDF("p", "mm", "a4");
  const pageHeight = 297; // A4 height in mm
  const marginBottom = 20;
  const maxY = pageHeight - marginBottom;
  let y = 20;

  // Helper function to check if we need a new page
  const checkPageBreak = (requiredSpace: number) => {
    if (y + requiredSpace > maxY) {
      pdf.addPage();
      y = 20; // Reset y position for new page
      return true;
    }
    return false;
  };

  // -------------------------------
  // Title Banner
  // -------------------------------
  pdf.setFillColor(30, 144, 255); // Blue
  pdf.rect(0, 0, 210, 25, "F");

  pdf.setFont("Helvetica", "bold");
  pdf.setFontSize(22);
  pdf.setTextColor(255, 255, 255);
  pdf.text("Interview Evaluation Report", 105, 16, { align: "center" });

  // Reset text color to black
  pdf.setTextColor(0, 0, 0);

  y += 20;

  // -------------------------------
  // Candidate Info Card
  // -------------------------------
  const infoLines = [
    `Candidate Name: ${displayName}`,
    `Email: ${displayEmail}`,
    `Position: ${displayRole}`,
    `Score: ${result.score}/10 (${getScoreLabel(result.score)})`,
    `Proctoring - Tab switches: ${result.tabSwitches ?? 0} | Left camera view: ${result.faceLostCount ?? 0}x (${result.faceLostSeconds ?? 0}s)`,
    `Proctoring - Multiple faces: ${result.multipleFacesCount ?? 0}x | Sudden movement: ${result.movementEvents ?? 0}x`,
  ];
  const boxHeight = infoLines.length * 7 + 8;
  checkPageBreak(boxHeight);
  pdf.setFillColor(245, 245, 245);
  pdf.roundedRect(10, y, 190, boxHeight, 3, 3, "F");

  pdf.setFontSize(12);
  pdf.setFont("Helvetica", "normal");

  infoLines.forEach((line, i) => {
    pdf.text(line, 15, y + 10 + i * 7);
  });

  y += boxHeight + 10;

  // -------------------------------
  // Section Header Function
  // -------------------------------
  const sectionHeader = (title: string) => {
    checkPageBreak(18);
    pdf.setDrawColor(30, 144, 255);
    pdf.setFillColor(30, 144, 255);
    pdf.roundedRect(10, y, 190, 10, 2, 2, "F");
    pdf.setFont("Helvetica", "bold");
    pdf.setFontSize(13);
    pdf.setTextColor(255, 255, 255);
    pdf.text(title, 15, y + 7);
    pdf.setTextColor(0, 0, 0);

    y += 18;
  };

  // -------------------------------
  // Feedback Section
  // -------------------------------
  sectionHeader("Overall Feedback");

  pdf.setFontSize(11);

  const styledLines = markdownToStyledLines(result.feedback);

  styledLines.forEach((lineObj) => {
    const { text, bold } = lineObj;

    pdf.setFont("Helvetica", bold ? "bold" : "normal");

    const wrapped = pdf.splitTextToSize(text, 180);
    const lineHeight = wrapped.length * 6 + (bold ? 4 : 2);
    
    checkPageBreak(lineHeight);
    pdf.text(wrapped, 15, y);
    y += lineHeight;
  });


  // -------------------------------
  // Areas for Improvement
  // -------------------------------
  if (result.areasForImprovement.length > 0) {
    sectionHeader("Areas For Improvement");

    result.areasForImprovement.forEach((area: string, i: number) => {
      const text = markdownToPlainText(`• ${area}`);
      const lines = pdf.splitTextToSize(text, 180);
      const lineHeight = lines.length * 6 + 4;
      
      checkPageBreak(lineHeight);
      pdf.text(lines, 15, y);
      y += lineHeight;
    });
  }

  // -------------------------------
  // Footer on last page
  // -------------------------------
  const totalPages = pdf.internal.pages.length - 1;
  for (let i = 1; i <= totalPages; i++) {
    pdf.setPage(i);
    pdf.setFontSize(10);
    pdf.setTextColor(120, 120, 120);
    pdf.text("Generated by AI Interview System", 105, 290, { align: "center" });
    pdf.text(`Page ${i} of ${totalPages}`, 105, 285, { align: "center" });
  }

  pdf.save(`Interview_Report_${displayName}.pdf`);
};


  if (isLoading) {
    return (
      <div className="min-h-screen bg-ink text-txt-hi font-display flex flex-col items-center justify-center px-6">
        <div className="vh-card-raised px-12 py-14 text-center max-w-md w-full animate-fade-up">
          <Loader2 className="h-9 w-9 animate-spin text-acc-cyan mx-auto mb-6" />
          <p className="text-lg font-medium tracking-tight">Analyzing your interview</p>
          <p className="mt-2 text-sm text-txt-mid vh-shimmer-text">
            The AI evaluator is reviewing every answer…
          </p>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="min-h-screen bg-ink text-txt-hi font-display flex flex-col items-center justify-center px-6">
        <div className="vh-card-raised px-10 py-12 text-center max-w-md w-full animate-fade-up">
          <div className="mx-auto h-14 w-14 rounded-2xl bg-[rgba(177,18,38,.1)] border border-[rgba(177,18,38,.25)] grid place-items-center mb-5">
            <AlertCircle className="h-7 w-7 text-[#E05860]" />
          </div>
          <p className="text-lg font-medium tracking-tight">Could not load results</p>
          <p className="mt-2 text-sm leading-relaxed text-txt-mid">{error}</p>
          <button onClick={onBack} className="vh-btn-ghost mt-8 px-6 py-2.5 text-sm mx-auto">
            <ArrowLeft className="h-4 w-4 text-txt-mid" />
            Go back
          </button>
        </div>
      </div>
    );
  }

  const roleLabel = displayRole.charAt(0).toUpperCase() + displayRole.slice(1);

  return (
    <div className="min-h-screen bg-ink text-txt-hi font-display antialiased selection:bg-acc-cyan/40">
      <header className="sticky top-0 z-20 backdrop-blur-xl bg-ink/[.82] border-b border-hairline">
        <div className="max-w-6xl mx-auto px-7 h-16 flex items-center justify-between">
          <button onClick={onBack} className="flex items-center gap-2 text-[13px] text-txt-mid hover:text-txt-hi transition-colors">
            <ArrowLeft className="h-[15px] w-[15px]" />
            Back
          </button>
          <span className="text-[14.5px] font-semibold tracking-[0.06em]">INTERVIEW REPORT</span>
          <span className="hidden sm:inline-flex"><PoweredByIScale /></span>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-7 py-10 grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">

        {/* LEFT SIDE - Candidate Info */}
        <aside className="space-y-6 animate-fade-up">
          <section className="vh-card p-6">
            <h2 className="text-[10.5px] font-medium uppercase tracking-[0.16em] text-txt-low mb-5">Candidate</h2>

            <div className="flex items-center gap-4">
              <div className="h-14 w-14 rounded-2xl overflow-hidden bg-surface-2 border border-hairline-strong grid place-items-center flex-shrink-0">
                {photo ? <img src={photo} className="h-full w-full object-cover" /> : <User className="h-[22px] w-[22px] text-txt-low" />}
              </div>
              <div className="min-w-0">
                <p className="font-semibold tracking-[-0.01em] truncate">{displayName}</p>
                <p className="text-[13px] text-txt-mid truncate">{displayEmail}</p>
              </div>
            </div>

            <div className="mt-[22px] space-y-2.5 text-sm">
              <div className="px-4 py-3 rounded-xl border border-hairline bg-[rgba(5,5,5,.5)] flex items-center gap-3">
                <Briefcase className="h-3.5 w-3.5 text-txt-low flex-shrink-0" />
                <span className="text-txt-mid text-[13px]">{roleLabel}</span>
              </div>
              <div className="px-4 py-3 rounded-xl border border-hairline bg-[rgba(5,5,5,.5)] flex items-center gap-3">
                <ListOrdered className="h-3.5 w-3.5 text-txt-low flex-shrink-0" />
                <span className="text-txt-mid text-[13px]">Questions: {totalQuestions}</span>
              </div>
              <div className="px-4 py-3 rounded-xl border border-hairline bg-[rgba(5,5,5,.5)] flex items-center gap-3">
                <CalendarClock className="h-3.5 w-3.5 text-txt-low flex-shrink-0" />
                <span className="text-txt-mid text-[13px]">Date: {new Date().toLocaleDateString()}</span>
              </div>

              {(() => {
                const flags = [
                  { label: "Tab switches", value: `${result.tabSwitches ?? 0}`, count: result.tabSwitches ?? 0 },
                  {
                    label: "Left camera view",
                    value: `${result.faceLostCount ?? 0}×${(result.faceLostSeconds ?? 0) > 0 ? ` (${result.faceLostSeconds}s total)` : ""}`,
                    count: result.faceLostCount ?? 0,
                  },
                  { label: "Multiple faces seen", value: `${result.multipleFacesCount ?? 0}×`, count: result.multipleFacesCount ?? 0 },
                  { label: "Sudden movement / out of frame", value: `${result.movementEvents ?? 0}×`, count: result.movementEvents ?? 0 },
                ];
                const anyFlag = flags.some((f) => (f.count ?? 0) > 0);
                return (
                  <div className={`px-4 py-3.5 rounded-xl border ${
                    anyFlag ? "border-amber-500/25 bg-amber-500/[0.07]" : "border-hairline bg-[rgba(5,5,5,.5)]"
                  }`}>
                    <p className={`flex items-center gap-2 text-[13px] font-medium mb-2.5 ${anyFlag ? "text-amber-300" : "text-txt-hi"}`}>
                      <AlertCircle className={`h-3.5 w-3.5 ${anyFlag ? "text-amber-400" : "text-acc-emerald"}`} />
                      Proctoring flags
                    </p>
                    <ul className="space-y-1.5 text-[11.5px]">
                      {flags.map((f) => (
                        <li key={f.label} className="flex justify-between gap-2">
                          <span className={anyFlag ? "text-amber-200/80" : "text-txt-mid"}>{f.label}</span>
                          <span className={`tabular-nums ${(f.count ?? 0) > 0 ? "text-amber-300 font-medium" : "text-txt-low"}`}>{f.value}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })()}
            </div>
          </section>

          {/* Score */}
          <section className="vh-card-raised p-7 text-center relative overflow-hidden">
            <h2 className="relative text-[10.5px] font-medium uppercase tracking-[0.16em] text-txt-low mb-5 flex items-center justify-center gap-2">
              <Award className="h-3.5 w-3.5 text-txt-low" />
              Overall score
            </h2>
            <div className={`relative text-7xl font-semibold tracking-[-0.04em] tabular-nums ${getScoreColor(result.score)}`}>
              {result.score}
            </div>
            <div className="relative text-[13px] text-txt-low mt-2 mb-6">out of 10</div>
            <div className={`relative px-[18px] py-2 rounded-full inline-flex items-center gap-2 text-[13px] font-medium border ${getScoreBgColor(result.score)}`}>
              {result.score >= 8 ? <ThumbsUp className="h-3.5 w-3.5" /> : result.score >= 6 ? <Star className="h-3.5 w-3.5" /> : <ThumbsDown className="h-3.5 w-3.5" />}
              {getScoreLabel(result.score)}
            </div>
          </section>

          {/* Actions */}
          <button onClick={downloadPDF} className="vh-btn-primary w-full py-3.5 text-[13.5px]">
            <Download className="h-4 w-4" />
            Download PDF report
          </button>
        </aside>

        {/* RIGHT SIDE - Feedback */}
        <div className="lg:col-span-2 space-y-6 animate-fade-up" style={{ animationDelay: "0.1s" }}>

          <section className="vh-card-raised p-8">
            <h2 className="text-[19px] tracking-[-0.02em] font-semibold mb-[22px] flex items-center gap-3.5">
              <span className="h-9 w-9 rounded-[11px] bg-[rgba(177,18,38,.08)] border border-[rgba(177,18,38,.35)] grid place-items-center">
                <FileText className="h-[15px] w-[15px] text-[#E05860]" />
              </span>
              Feedback
            </h2>
            <div className="prose prose-invert prose-p:text-txt-mid prose-li:text-txt-mid prose-headings:tracking-tight max-w-none">
              <ReactMarkdown>{formatMarkdown(result.feedback)}</ReactMarkdown>
            </div>
          </section>

          {result.areasForImprovement.length > 0 && (
            <section className="vh-card p-8">
              <h2 className="text-[19px] tracking-[-0.02em] font-semibold text-acc-copper mb-5 flex items-center gap-3.5">
                <span className="h-9 w-9 rounded-[11px] bg-[rgba(201,154,114,.07)] border border-[rgba(201,154,114,.28)] grid place-items-center">
                  <Target className="h-[15px] w-[15px] text-acc-copper" />
                </span>
                Areas for improvement
              </h2>
              <ul className="space-y-3">
                {result.areasForImprovement.map((area, idx) => (
                  <li
                    key={idx}
                    className="px-5 py-4 rounded-xl border border-[rgba(201,154,114,.14)] bg-[rgba(201,154,114,.05)] text-sm leading-relaxed text-[#CBAE96]"
                  >
                    {area}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="vh-card p-8">
            <h2 className="text-[19px] tracking-[-0.02em] font-semibold flex items-center gap-3.5">
              <span className="h-9 w-9 rounded-[11px] bg-[rgba(95,164,127,.08)] border border-[rgba(95,164,127,.3)] grid place-items-center">
                <TrendingUp className="h-[15px] w-[15px] text-acc-emerald" />
              </span>
              Performance breakdown
            </h2>
            <div className="mt-7 space-y-6">
              {["Communication Skills", "Technical Knowledge", "Overall Impression"].map((label) => (
                <div key={label}>
                  <div className="flex items-center justify-between mb-2.5">
                    <span className="text-[13.5px] text-txt-mid">{label}</span>
                    <span className="text-[13.5px] font-medium tabular-nums text-txt-hi">
                      {result.score * 10}%
                    </span>
                  </div>
                  <div className="h-[7px] bg-[#26272B] rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-1000 ease-out"
                      style={{
                        width: `${result.score * 10}%`,
                        background: "linear-gradient(90deg,#6E0F1E,#B11226)",
                      }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </section>

        </div>

      </main>

      <footer className="border-t border-hairline">
        <div className="max-w-6xl mx-auto px-7 py-[18px] flex flex-col sm:flex-row items-center justify-center gap-3 text-[13px] text-txt-low">
          <span>© {new Date().getFullYear()} VoxHire. All rights reserved.</span>
          <PoweredByIScale />
        </div>
      </footer>
    </div>
  );
}
