import { Link } from "wouter";
import {
  Mic,
  ArrowRight,
  Lock,
  CheckCircle2,
  Clock,
  ListOrdered,
  AudioLines,
  UserCheck,
  VolumeX,
  Wifi,
  ShieldCheck,
  Timer,
} from "lucide-react";
import PoweredByIScale from "@/components/PoweredByIScale";

const CHECKLIST = [
  { icon: VolumeX, text: "Find a quiet environment" },
  { icon: Mic, text: "Allow microphone access when prompted" },
  { icon: Wifi, text: "Use a stable internet connection" },
  { icon: Timer, text: "Complete the interview in one sitting" },
  { icon: ShieldCheck, text: "Responses are securely stored" },
];

const INTERVIEW_FACTS = [
  { icon: Clock, label: "Estimated duration", value: "10–15 minutes" },
  { icon: ListOrdered, label: "Assessment scope", value: "9–10 questions, adapts as you go" },
  { icon: AudioLines, label: "Interview mode", value: "Voice AI" },
  { icon: UserCheck, label: "Evaluation", value: "AI + recruiter review" },
];

// Decorative waveform bars — every 5th bar tinted crimson, gentle scaleY drift
const WAVE_BARS = Array.from({ length: 36 }, (_, i) => {
  const a = Math.abs(Math.sin(i * 0.9)) * 0.7 + Math.abs(Math.sin(i * 0.31)) * 0.3;
  return {
    h: 8 + Math.round(a * 30),
    dur: (1.7 + (i % 5) * 0.28).toFixed(2),
    delay: (-(i * 0.13)).toFixed(2),
    accent: i % 5 === 2,
  };
});

export default function Home() {
  return (
    <div className="min-h-screen bg-ink text-txt-hi font-display antialiased selection:bg-acc-cyan/40 flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-20 backdrop-blur-xl bg-ink/[.82] border-b border-hairline">
        <div className="max-w-5xl mx-auto px-7 h-16 flex items-center justify-between">
          <div className="flex flex-col leading-tight">
            <span className="text-[15px] font-bold tracking-[0.1em]">VOXHIRE</span>
            <span className="text-[9.5px] font-medium tracking-[0.2em] text-txt-low uppercase">AI Interview Platform</span>
          </div>
          <PoweredByIScale />
        </div>
      </header>

      <main className="flex-1 w-full max-w-[1200px] mx-auto px-8 py-6 grid grid-cols-1 lg:grid-cols-[1.05fr_1fr] gap-14 items-start">
        {/* Hero */}
        <section className="relative text-left pt-0 lg:pt-9 animate-fade-up">
          <div
            className="pointer-events-none absolute -top-[10%] -left-[14%] w-[125%] h-[115%] blur-3xl"
            style={{ background: "radial-gradient(55% 45% at 38% 35%, #B1122614, transparent 70%)" }}
          />
          <div className="vh-badge relative">
            <span className="h-1.5 w-1.5 rounded-full bg-acc-cyan animate-pulse" />
            Welcome — your AI interview is ready
          </div>
          <h1 className="relative mt-6 text-[2.6rem] leading-[1.06] sm:text-[52px] tracking-[-0.03em] font-semibold">
            Your AI Interview
            <br />
            <span className="text-txt-mid">Starts Here</span>
          </h1>
          <p className="relative mt-5 max-w-[480px] text-[16.5px] leading-[1.65] text-txt-mid">
            Complete your interview using voice responses. Your answers are
            securely analyzed and reviewed by The iScale hiring team.
          </p>
          <div className="relative mt-8 flex items-center justify-start gap-3.5 flex-wrap">
            <Link href="/interview">
              <button className="vh-btn-primary group px-8 py-4 text-[15px]">
                <Mic className="h-[17px] w-[17px]" />
                Start Interview
                <ArrowRight className="h-[15px] w-[15px] transition-transform duration-200 group-hover:translate-x-0.5" />
              </button>
            </Link>
            <Link href="/admin">
              <button className="group inline-flex items-center gap-2.5 whitespace-nowrap rounded-xl border border-[rgba(201,154,114,.3)] bg-[rgba(201,154,114,.05)] px-6 py-4 text-[14.5px] font-medium text-acc-copper transition-all duration-200 hover:-translate-y-px hover:border-[rgba(201,154,114,.55)] hover:bg-[rgba(201,154,114,.1)]">
                <Lock className="h-3.5 w-3.5" />
                Admin
              </button>
            </Link>
          </div>
          <div className="relative mt-[52px] flex items-center gap-1 h-11 max-w-[420px] justify-start">
            {WAVE_BARS.map((b, i) => (
              <span
                key={i}
                className={`vh-wave-bar w-[3px] rounded-full flex-shrink-0 ${b.accent ? "bg-acc-cyan/60" : "bg-surface-3"}`}
                style={{
                  height: `${b.h}px`,
                  transformOrigin: "center",
                  ["--wave-dur" as never]: `${b.dur}s`,
                  ["--wave-delay" as never]: `${b.delay}s`,
                }}
              />
            ))}
          </div>
          <p className="relative mt-3 text-[10.5px] font-medium tracking-[0.18em] uppercase text-txt-low">
            Voice-first · Proctored · Reviewed by humans
          </p>
        </section>

        {/* Before You Begin */}
        <section id="guidelines" className="scroll-mt-24">
          <div
            className="vh-card overflow-hidden animate-fade-up transition-shadow duration-300"
            style={{ boxShadow: "inset 0 1px 0 rgba(255,255,255,.04), 0 20px 50px rgba(0,0,0,.5), 0 0 80px #B112260A" }}
          >
            <div className="px-7 pt-[22px] pb-[18px] border-b border-hairline">
              <h2 className="text-lg tracking-[-0.02em] font-semibold">Before You Begin</h2>
              <p className="mt-1.5 text-[13px] text-txt-mid">
                A quick checklist so your interview goes smoothly.
              </p>
            </div>

            <div className="px-7 py-6 flex flex-col gap-[22px]">
              {CHECKLIST.map(({ icon: Icon, text }, i) => (
                <div
                  key={text}
                  className="flex items-center gap-4 animate-fade-up"
                  style={{ animationDelay: `${0.2 + i * 0.08}s` }}
                >
                  <span className="h-9 w-9 rounded-[10px] bg-surface-2 border border-hairline grid place-items-center flex-shrink-0">
                    <Icon className="h-[15px] w-[15px]" style={{ color: "color-mix(in oklab, #B11226 65%, #B3B3B8)" }} />
                  </span>
                  <span className="flex-1 text-[14.5px] text-txt-mid">{text}</span>
                  <CheckCircle2 className="h-[15px] w-[15px] text-acc-emerald/70 flex-shrink-0" />
                </div>
              ))}
            </div>

            <div className="mx-7 h-px bg-hairline" />

            <div className="px-7 py-[22px] grid grid-cols-2 gap-3">
              {INTERVIEW_FACTS.map(({ icon: Icon, label, value }) => (
                <div key={label} className="rounded-xl border border-hairline bg-bg-2 p-4 transition-colors duration-200 hover:border-hairline-strong">
                  <Icon className="h-[15px] w-[15px] text-txt-low mb-3" />
                  <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-txt-low">{label}</p>
                  <p className="text-[13.5px] font-medium text-txt-hi mt-1">{value}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-hairline">
        <div className="max-w-5xl mx-auto px-7 py-[18px] flex items-center justify-between gap-4 text-[13px] text-txt-low">
          <p>© {new Date().getFullYear()} VoxHire. All rights reserved.</p>
          <PoweredByIScale />
        </div>
      </footer>
    </div>
  );
}
