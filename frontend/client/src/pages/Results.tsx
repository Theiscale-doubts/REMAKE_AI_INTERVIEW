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
  RotateCw,
  FileText,
} from "lucide-react";

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
        if (!response.ok) throw new Error("Unable to fetch results");

        const data = await response.json();
        const areasForImprovement = parseAreasForImprovement(data.feedback);

        setResult({
          score: data.score || 0,
          feedback: data.feedback || "",
          areasForImprovement,
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
    if (score >= 8) return "text-emerald-400";
    if (score >= 6) return "text-yellow-400";
    return "text-rose-400";
  };

  const getScoreBgColor = (score: number) => {
    if (score >= 8) return "bg-emerald-600/20 border-emerald-500/30";
    if (score >= 6) return "bg-yellow-600/20 border-yellow-500/30";
    return "bg-rose-600/20 border-rose-500/30";
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
  checkPageBreak(35);
  pdf.setFillColor(245, 245, 245);
  pdf.roundedRect(10, y, 190, 35, 3, 3, "F");

  pdf.setFontSize(12);
  pdf.setFont("Helvetica", "normal");

  pdf.text(`Candidate Name: ${name}`, 15, y + 10);
  pdf.text(`Email: ${email}`, 15, y + 17);
  pdf.text(`Position: ${role}`, 15, y + 24);
  pdf.text(`Score: ${result.score}/10 (${getScoreLabel(result.score)})`, 15, y + 31);

  y += 45;

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

  pdf.save(`Interview_Report_${name}.pdf`);
};


  if (isLoading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-white">
        <Loader2 className="h-12 w-12 animate-spin text-indigo-400 mb-4" />
        <p className="text-lg">Analyzing interview results...</p>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-white">
        <AlertCircle className="h-10 w-10 text-rose-500" />
        <p className="mt-4">{error}</p>
      </div>
    );
  }

  const roleLabel = role.charAt(0).toUpperCase() + role.slice(1);

  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      <header className="sticky top-0 bg-neutral-950/80 backdrop-blur border-b border-white/10 p-5 flex items-center justify-between">
        <button onClick={onBack} className="flex items-center gap-2 hover:opacity-80">
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-10 grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* LEFT SIDE - Candidate Info */}
        <aside className="space-y-6">
          <section className="rounded-xl border border-white/10 bg-white/5 p-6">
            <h2 className="text-lg font-semibold mb-4">Candidate</h2>

            <div className="flex items-center gap-4">
              <div className="h-16 w-16 rounded-full overflow-hidden bg-neutral-900 border border-white/10">
                {photo ? <img src={photo} className="h-full w-full object-cover" /> : <User className="mx-auto mt-5" />}
              </div>

              <div>
                <p className="font-semibold">{name}</p>
                <p className="text-sm text-neutral-400">{email}</p>
              </div>
            </div>

            <div className="mt-6 space-y-3 text-sm">
              <div className="p-3 rounded-lg border border-white/10 bg-white/5 flex gap-2">
                <Briefcase className="h-4 w-4 text-indigo-400" />
                {roleLabel}
              </div>

              <div className="p-3 rounded-lg border border-white/10 bg-white/5">
                <ListOrdered className="h-4 w-4 mb-1" />
                Questions: {totalQuestions}
              </div>

              <div className="p-3 rounded-lg border border-white/10 bg-white/5">
                <CalendarClock className="h-4 w-4 mb-1" />
                Date: {new Date().toLocaleDateString()}
              </div>
            </div>
          </section>

          {/* Score */}
          <section className={`rounded-xl border ${getScoreBgColor(result.score)} p-6 text-center`}>
            <h2 className="font-semibold text-lg mb-4 flex items-center justify-center gap-2">
              <Award className="h-5 w-5 text-indigo-400" />
              Score
            </h2>

            <div className="text-6xl font-bold mb-3">{result.score}</div>
            <div className="text-sm text-neutral-400 mb-4">out of 10</div>

            <div className={`px-4 py-2 rounded-full inline-flex items-center gap-2 ${getScoreBgColor(result.score)}`}>
              {result.score >= 8 ? <ThumbsUp /> : result.score >= 6 ? <Star /> : <ThumbsDown />}
              {getScoreLabel(result.score)}
            </div>
          </section>

          {/* Download Buttons */}
          <button
            onClick={downloadPDF}
            className="w-full bg-green-600 hover:bg-green-500 p-3 rounded-lg flex items-center justify-center gap-2"
          >
            <Download className="h-4 w-4" />
            Download PDF Report
          </button>

          <button
            onClick={onBack}
            className="w-full bg-white/10 hover:bg-white/20 p-3 rounded-lg flex items-center justify-center gap-2"
          >
            <RotateCw className="h-4 w-4" />
            New Interview
          </button>
        </aside>

        {/* RIGHT SIDE - Feedback */}
        <div className="lg:col-span-2 space-y-6">

          <section className="rounded-xl border border-white/10 bg-white/5 p-6">
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <FileText className="h-5 w-5 text-indigo-400" />
              Feedback
            </h2>

          <div className="prose prose-invert max-w-none">
            <ReactMarkdown>{formatMarkdown(result.feedback)}</ReactMarkdown>
          </div>
          </section>

          {result.areasForImprovement.length > 0 && (
            <section className="rounded-xl border border-amber-500/30 bg-amber-600/10 p-6">
              <h2 className="text-xl font-semibold text-amber-200 mb-4 flex items-center gap-2">
                <Target className="h-5 w-5 text-amber-400" />
                Areas for Improvement
              </h2>

              <ul className="space-y-3">
                {result.areasForImprovement.map((area, idx) => (
                  <li
                    key={idx}
                    className="p-3 rounded border border-amber-500/20 bg-amber-600/5 text-amber-100"
                  >
                    {area}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="rounded-xl border border-white/10 bg-white/5 p-6">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-indigo-400" />
              Performance Breakdown
            </h2>

            <div className="mt-4 space-y-6">
              {/* Progress Bars */}
              {["Communication Skills", "Technical Knowledge", "Overall Impression"].map((label) => (
                <div key={label}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm text-neutral-400">{label}</span>
                    <span className={`text-sm font-medium ${getScoreColor(result.score)}`}>
                      {result.score * 10}%
                    </span>
                  </div>

                  <div className="h-2 bg-neutral-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${result.score >= 8
                        ? "bg-emerald-500"
                        : result.score >= 6
                        ? "bg-yellow-500"
                        : "bg-rose-500"}`}
                      style={{ width: `${result.score * 10}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </section>

        </div>

      </main>

      <footer className="text-center text-neutral-500 py-6 text-sm border-t border-white/10">
        © {new Date().getFullYear()} VoxHire. All Rights Reserved.
      </footer>
    </div>
  );
}
