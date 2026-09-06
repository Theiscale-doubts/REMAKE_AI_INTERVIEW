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
import SiteFooter from "@/components/SiteFooter";
import { roleLabel } from "@/roles";

const API_BASE_URL = `${(import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "")}/api`;
// Empty (the default in .env.production) omits the credit from the PDF footer.
const AUTHOR_NAME = import.meta.env.VITE_AUTHOR_NAME || "";
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
  communication: number;
  technical: number;
  problemSolving: number;
  photo?: string;
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
          communication: data.communication ?? 0,
          technical: data.technical ?? 0,
          problemSolving: data.problem_solving ?? 0,
          photo: data.photo || "",
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
  // Prefer a photo passed in as a prop; otherwise use the interview-time snapshot
  // returned by the backend (shown when the report is opened via session ID).
  const displayPhoto = photo || result?.photo || null;

 // Brand palette — pulled straight from index.css custom properties so the
 // PDF is the same theme as the site, not a generic jsPDF default look.
 const PDF_COLORS = {
   ink: [5, 5, 5] as [number, number, number],
   surface: [23, 24, 27] as [number, number, number],
   hairline: [45, 46, 50] as [number, number, number],
   crimson: [177, 18, 38] as [number, number, number],
   crimsonBright: [200, 29, 37] as [number, number, number],
   emerald: [95, 164, 127] as [number, number, number],
   copper: [201, 154, 114] as [number, number, number],
   red: [217, 43, 50] as [number, number, number],
   textHi: [245, 245, 245] as [number, number, number],
   textMid: [179, 179, 184] as [number, number, number],
   textLow: [124, 124, 132] as [number, number, number],
 };

 // jsPDF's built-in Helvetica only has correct glyph-width metrics for basic
 // WinAnsi/Latin-1 characters. LLM-generated feedback routinely includes
 // "smart" typography (non-breaking hyphens, curly quotes, em-dashes,
 // ellipses) that this font can't measure correctly — left unsanitized, that
 // silently corrupts splitTextToSize's line-wrap math and text overflows the
 // page margin. Normalize to safe ASCII equivalents before anything reaches jsPDF.
 const sanitizeForPdf = (text: string): string =>
   text
     // curly/smart single quotes -> straight apostrophe
     .replace(/[\u2018\u2019\u201A\u201B]/g, "'")
     // curly/smart double quotes -> straight quote
     .replace(/[\u201C\u201D\u201E\u201F]/g, '"')
     // hyphen variants, non-breaking hyphen, figure/en/em dash, horizontal bar -> "-"
     .replace(/[\u2010\u2011\u2012\u2013\u2014\u2015]/g, "-")
     // ellipsis -> "..."
     .replace(/\u2026/g, "...")
     // non-breaking space and other Unicode space variants -> normal space
     .replace(/[\u00A0\u2000-\u200A\u202F\u205F]/g, " ")
     // bullet-ish glyphs that survived markdown parsing -> "-"
     .replace(/[\u2022\u25CF\u25E6\u2023]/g, "-");

 const getScoreRGB = (score: number): [number, number, number] => {
   if (score >= 8) return PDF_COLORS.emerald;
   if (score >= 6) return PDF_COLORS.copper;
   return PDF_COLORS.red;
 };

 const downloadPDF = () => {
  if (!result) return;

  const pdf = new jsPDF("p", "mm", "a4");
  const pageWidth = 210;
  const pageHeight = 297; // A4 height in mm
  const marginX = 16;
  const contentWidth = pageWidth - marginX * 2;
  const marginBottom = 24;
  const maxY = pageHeight - marginBottom;
  let y = 20;

  // Every page — including the first, which jsPDF creates implicitly — needs
  // the dark ink background painted before anything else is drawn on it.
  const paintPageBackground = () => {
    pdf.setFillColor(...PDF_COLORS.ink);
    pdf.rect(0, 0, pageWidth, pageHeight, "F");
  };

  // Translucent fills (matching the site's soft rgba tinted cards) via jsPDF's
  // graphics-state opacity, restored immediately after each use.
  const withOpacity = (opacity: number, draw: () => void) => {
    pdf.saveGraphicsState();
    // @ts-ignore — GState is attached to the jsPDF instance at runtime
    pdf.setGState(new pdf.GState({ opacity }));
    draw();
    pdf.restoreGraphicsState();
  };

  const footer = () => {
    pdf.setFont("Helvetica", "normal");
    pdf.setFontSize(8.5);
    pdf.setTextColor(...PDF_COLORS.textLow);
    pdf.text("VoxHire — Powered by The iScale", marginX, pageHeight - 12);
    if (AUTHOR_NAME) {
      pdf.text(`Developed & managed by ${AUTHOR_NAME}`, pageWidth - marginX, pageHeight - 12, { align: "right" });
    }
  };

  paintPageBackground();

  const checkPageBreak = (requiredSpace: number) => {
    if (y + requiredSpace > maxY) {
      footer();
      pdf.addPage();
      paintPageBackground();
      y = 20;
      return true;
    }
    return false;
  };

  // -------------------------------
  // Header — brand wordmark, matching the site's top nav
  // -------------------------------
  pdf.setFont("Helvetica", "bold");
  pdf.setFontSize(19);
  pdf.setTextColor(...PDF_COLORS.textHi);
  pdf.text("VOXHIRE", marginX, y);

  pdf.setFont("Helvetica", "normal");
  pdf.setFontSize(8.5);
  pdf.setTextColor(...PDF_COLORS.textLow);
  pdf.text("I N T E R V I E W   E V A L U A T I O N   R E P O R T", marginX, y + 6);

  // Candidate verification snapshot — a framed badge in the top-right of the
  // header. Wrapped so a missing/invalid image never aborts the PDF; if it
  // fails, the report simply generates without the photo.
  if (displayPhoto && typeof displayPhoto === "string" && displayPhoto.startsWith("data:image")) {
    try {
      const fmt = displayPhoto.includes("image/png") ? "PNG" : "JPEG";
      pdf.setFillColor(...PDF_COLORS.surface);
      pdf.setDrawColor(...PDF_COLORS.hairline);
      pdf.roundedRect(pageWidth - marginX - 20, 3, 20, 20, 3, 3, "FD");
      pdf.addImage(displayPhoto, fmt, pageWidth - marginX - 19, 4, 18, 18);
    } catch (e) {
      console.warn("Skipped candidate photo in PDF:", e);
    }
  }

  y += 14;
  pdf.setDrawColor(...PDF_COLORS.hairline);
  pdf.setLineWidth(0.3);
  pdf.line(marginX, y, pageWidth - marginX, y);
  y += 10;

  // -------------------------------
  // Candidate info card
  // -------------------------------
  const infoRows: [string, string][] = [
    ["Candidate", sanitizeForPdf(displayName)],
    ["Email", sanitizeForPdf(displayEmail)],
    ["Position", sanitizeForPdf(roleLabel(displayRole))],
  ];
  const cardPad = 6;
  const rowH = 6.5;
  const cardH = infoRows.length * rowH + cardPad * 2;
  checkPageBreak(cardH);

  pdf.setFillColor(...PDF_COLORS.surface);
  pdf.setDrawColor(...PDF_COLORS.hairline);
  pdf.roundedRect(marginX, y, contentWidth, cardH, 3, 3, "FD");

  pdf.setFontSize(10.5);
  infoRows.forEach(([label, value], i) => {
    const rowY = y + cardPad + 4 + i * rowH;
    pdf.setFont("Helvetica", "normal");
    pdf.setTextColor(...PDF_COLORS.textLow);
    pdf.text(label, marginX + 6, rowY);
    pdf.setFont("Helvetica", "bold");
    pdf.setTextColor(...PDF_COLORS.textHi);
    pdf.text(value || "—", marginX + 45, rowY);
  });

  y += cardH + 8;

  // -------------------------------
  // Score card
  // -------------------------------
  const scoreRGB = getScoreRGB(result.score);
  const scoreCardH = 34;
  checkPageBreak(scoreCardH);

  pdf.setFillColor(...PDF_COLORS.surface);
  pdf.setDrawColor(...PDF_COLORS.hairline);
  pdf.roundedRect(marginX, y, contentWidth, scoreCardH, 3, 3, "FD");

  pdf.setFont("Helvetica", "normal");
  pdf.setFontSize(8.5);
  pdf.setTextColor(...PDF_COLORS.textLow);
  pdf.text("OVERALL SCORE", marginX + 8, y + 10);

  pdf.setFont("Helvetica", "bold");
  pdf.setFontSize(28);
  pdf.setTextColor(...scoreRGB);
  pdf.text(`${result.score}`, marginX + 8, y + 24);
  const scoreNumWidth = pdf.getTextWidth(`${result.score}`);
  pdf.setFont("Helvetica", "normal");
  pdf.setFontSize(11);
  pdf.setTextColor(...PDF_COLORS.textLow);
  pdf.text("/10", marginX + 8 + scoreNumWidth + 2, y + 24);

  // Score label pill
  const label = getScoreLabel(result.score);
  pdf.setFont("Helvetica", "bold");
  pdf.setFontSize(10);
  const pillTextW = pdf.getTextWidth(label);
  const pillW = pillTextW + 12;
  const pillX = pageWidth - marginX - 8 - pillW;
  const pillY = y + scoreCardH / 2 - 5;
  withOpacity(0.14, () => {
    pdf.setFillColor(...scoreRGB);
    pdf.roundedRect(pillX, pillY, pillW, 10, 5, 5, "F");
  });
  pdf.setTextColor(...scoreRGB);
  pdf.text(label, pillX + pillW / 2, pillY + 6.7, { align: "center" });

  y += scoreCardH + 8;

  // -------------------------------
  // Proctoring flags card
  // -------------------------------
  const flags: [string, number, string][] = [
    ["Focus & copy flags", result.tabSwitches ?? 0, `${result.tabSwitches ?? 0}×`],
    ["Left camera view", result.faceLostCount ?? 0, `${result.faceLostCount ?? 0}×${(result.faceLostSeconds ?? 0) > 0 ? ` (${result.faceLostSeconds}s)` : ""}`],
    ["Multiple faces seen", result.multipleFacesCount ?? 0, `${result.multipleFacesCount ?? 0}×`],
    ["Sudden movement", result.movementEvents ?? 0, `${result.movementEvents ?? 0}×`],
  ];
  const anyFlag = flags.some(([, count]) => count > 0);
  const flagRowH = 6;
  const flagCardH = flags.length * flagRowH + cardPad * 2 + 4;
  checkPageBreak(flagCardH);

  if (anyFlag) {
    withOpacity(0.08, () => {
      pdf.setFillColor(...PDF_COLORS.copper);
      pdf.roundedRect(marginX, y, contentWidth, flagCardH, 3, 3, "F");
    });
    pdf.setDrawColor(...PDF_COLORS.copper);
  } else {
    pdf.setFillColor(...PDF_COLORS.surface);
    pdf.setDrawColor(...PDF_COLORS.hairline);
    pdf.roundedRect(marginX, y, contentWidth, flagCardH, 3, 3, "FD");
  }
  if (anyFlag) {
    pdf.setLineWidth(0.3);
    pdf.roundedRect(marginX, y, contentWidth, flagCardH, 3, 3, "D");
  }

  pdf.setFont("Helvetica", "bold");
  pdf.setFontSize(9);
  pdf.setTextColor(...(anyFlag ? PDF_COLORS.copper : PDF_COLORS.textHi));
  pdf.text("PROCTORING FLAGS", marginX + 6, y + cardPad + 2);

  pdf.setFontSize(9.5);
  flags.forEach(([flabel, count, fvalue], i) => {
    const rowY = y + cardPad + 9 + i * flagRowH;
    pdf.setFont("Helvetica", "normal");
    pdf.setTextColor(...(count > 0 ? PDF_COLORS.copper : PDF_COLORS.textMid));
    pdf.text(flabel, marginX + 6, rowY);
    pdf.setFont("Helvetica", count > 0 ? "bold" : "normal");
    pdf.setTextColor(...(count > 0 ? PDF_COLORS.copper : PDF_COLORS.textLow));
    pdf.text(fvalue, pageWidth - marginX - 6, rowY, { align: "right" });
  });

  y += flagCardH + 10;

  // -------------------------------
  // Section header — accent bar + tracked-caps label, not a solid banner
  // -------------------------------
  const sectionHeader = (title: string, rgb: [number, number, number] = PDF_COLORS.crimsonBright) => {
    checkPageBreak(14);
    pdf.setFillColor(...rgb);
    pdf.roundedRect(marginX, y - 3.2, 2.4, 6, 1.2, 1.2, "F");
    pdf.setFont("Helvetica", "bold");
    pdf.setFontSize(12.5);
    pdf.setTextColor(...PDF_COLORS.textHi);
    pdf.text(title, marginX + 6, y);
    y += 10;
  };

  // -------------------------------
  // Feedback section
  // -------------------------------
  sectionHeader("Overall Feedback");

  const styledLines = markdownToStyledLines(sanitizeForPdf(result.feedback));

  styledLines.forEach((lineObj) => {
    const { text, bold } = lineObj;

    pdf.setFont("Helvetica", bold ? "bold" : "normal");
    pdf.setFontSize(bold ? 11.5 : 10.5);
    pdf.setTextColor(...(bold ? PDF_COLORS.textHi : PDF_COLORS.textMid));

    const wrapped = pdf.splitTextToSize(text, contentWidth - 4);
    const lineHeight = wrapped.length * 5.6 + (bold ? 4 : 2);

    checkPageBreak(lineHeight);
    pdf.text(wrapped, marginX + 2, y);
    y += lineHeight;
  });

  y += 4;

  // -------------------------------
  // Areas for Improvement — copper-accented cards, matching the site
  // -------------------------------
  if (result.areasForImprovement.length > 0) {
    sectionHeader("Areas For Improvement", PDF_COLORS.copper);

    result.areasForImprovement.forEach((area: string) => {
      const text = markdownToPlainText(sanitizeForPdf(area));
      pdf.setFont("Helvetica", "normal");
      pdf.setFontSize(10);
      const lines = pdf.splitTextToSize(text, contentWidth - 14);
      const rowH2 = lines.length * 5.2 + 8;

      checkPageBreak(rowH2);
      withOpacity(0.06, () => {
        pdf.setFillColor(...PDF_COLORS.copper);
        pdf.roundedRect(marginX, y - 4, contentWidth, rowH2, 2, 2, "F");
      });
      pdf.setFillColor(...PDF_COLORS.copper);
      pdf.rect(marginX, y - 4, 1, rowH2, "F");
      pdf.setTextColor(...PDF_COLORS.copper);
      pdf.text(lines, marginX + 6, y);
      y += rowH2 + 3;
    });
  }

  // -------------------------------
  // Footer on every page
  // -------------------------------
  const totalPages = pdf.internal.pages.length - 1;
  for (let i = 1; i <= totalPages; i++) {
    pdf.setPage(i);
    footer();
    pdf.setFontSize(8.5);
    pdf.setTextColor(...PDF_COLORS.textLow);
    pdf.text(`Page ${i} of ${totalPages}`, pageWidth / 2, pageHeight - 12, { align: "center" });
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

  const roleTitle = roleLabel(displayRole);

  return (
    <div className="min-h-screen bg-ink text-txt-hi font-display antialiased selection:bg-acc-cyan/40">
      <header className="sticky top-0 z-20 backdrop-blur-xl bg-ink/[.82] border-b border-hairline">
        <div className="max-w-6xl mx-auto px-4 sm:px-7 h-16 flex items-center justify-between gap-3">
          <button onClick={onBack} className="flex items-center gap-2 text-[13px] text-txt-mid hover:text-txt-hi transition-colors">
            <ArrowLeft className="h-[15px] w-[15px]" />
            Back
          </button>
          <span className="text-[12px] sm:text-[14.5px] font-semibold tracking-[0.06em] truncate">INTERVIEW REPORT</span>
          <span className="hidden sm:inline-flex"><PoweredByIScale /></span>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-7 py-6 sm:py-10 grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">

        {/* LEFT SIDE - Candidate Info */}
        <aside className="space-y-6 animate-fade-up">
          <section className="vh-card p-5 sm:p-6">
            <h2 className="text-[10.5px] font-medium uppercase tracking-[0.16em] text-txt-low mb-5">Candidate</h2>

            <div className="flex items-center gap-4">
              <div className="h-14 w-14 rounded-2xl overflow-hidden bg-surface-2 border border-hairline-strong grid place-items-center flex-shrink-0">
                {displayPhoto ? <img src={displayPhoto} className="h-full w-full object-cover" /> : <User className="h-[22px] w-[22px] text-txt-low" />}
              </div>
              <div className="min-w-0">
                <p className="font-semibold tracking-[-0.01em] truncate">{displayName}</p>
                <p className="text-[13px] text-txt-mid truncate">{displayEmail}</p>
              </div>
            </div>

            <div className="mt-[22px] space-y-2.5 text-sm">
              <div className="px-4 py-3 rounded-xl border border-hairline bg-[rgba(5,5,5,.5)] flex items-center gap-3">
                <Briefcase className="h-3.5 w-3.5 text-txt-low flex-shrink-0" />
                <span className="text-txt-mid text-[13px]">{roleTitle}</span>
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
                  { label: "Focus & copy flags", value: `${result.tabSwitches ?? 0}`, count: result.tabSwitches ?? 0 },
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
          <section className="vh-card-raised p-5 sm:p-7 text-center relative overflow-hidden">
            <h2 className="relative text-[10.5px] font-medium uppercase tracking-[0.16em] text-txt-low mb-5 flex items-center justify-center gap-2">
              <Award className="h-3.5 w-3.5 text-txt-low" />
              Overall score
            </h2>
            <div className={`relative text-6xl sm:text-7xl font-semibold tracking-[-0.04em] tabular-nums ${getScoreColor(result.score)}`}>
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

          <section className="vh-card-raised p-5 sm:p-8">
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
              {[
                { label: "Communication Skills", value: result.communication },
                { label: "Technical Knowledge", value: result.technical },
                { label: "Problem-Solving", value: result.problemSolving },
              ].map(({ label, value }) => {
                const pct = Math.max(0, Math.min(value, 100));
                return (
                  <div key={label}>
                    <div className="flex items-center justify-between mb-2.5">
                      <span className="text-[13.5px] text-txt-mid">{label}</span>
                      <span className="text-[13.5px] font-medium tabular-nums text-txt-hi">
                        {pct}%
                      </span>
                    </div>
                    <div className="h-[7px] bg-[#26272B] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-1000 ease-out"
                        style={{
                          width: `${pct}%`,
                          background: "linear-gradient(90deg,#6E0F1E,#B11226)",
                        }}
                      ></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

        </div>

      </main>

      <SiteFooter maxWidth="max-w-6xl" />
    </div>
  );
}
