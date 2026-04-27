import { Link } from "wouter";
import { Button } from "@/components/ui/button";
import {
  Mic,
  Shield,
  BarChart3,
  Timer,
  UploadCloud,
  Sliders,
  ArrowRight,
  ClipboardList,
  Briefcase,
  Headphones,
  ClipboardCheck,
} from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      {/* Decorative background */}
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div
          className="absolute -top-32 left-1/2 -translate-x-1/2 h-[36rem] w-[36rem] rounded-full blur-3xl opacity-40 animate-spin"
          style={{
            background:
              "conic-gradient(from 90deg at 50% 50%, rgba(99,102,241,0.25), rgba(16,185,129,0.15), rgba(99,102,241,0.25))",
            animationDuration: "18s",
          }}
        />
        <div
          className="absolute bottom-[-18rem] right-[-8rem] h-[28rem] w-[28rem] rounded-full blur-3xl opacity-30"
          style={{
            background:
              "radial-gradient(60% 60% at 50% 50%, rgba(34,197,94,0.25), transparent)",
          }}
        />
      </div>

      {/* Header */}
      <header className="sticky top-0 z-20 backdrop-blur supports-[backdrop-filter]:bg-neutral-950/60 bg-neutral-950/80 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/">
            <div className="flex items-center gap-3 cursor-pointer">
              <div className="h-8 w-8 grid place-items-center rounded-md bg-white text-neutral-900 font-semibold tracking-tight">
                VH
              </div>
              <div className="flex flex-col">
                <span className="text-lg tracking-tight font-semibold">
                  VoxHire
                </span>
                <span className="text-xs text-neutral-400">
                  Voice-first interviews
                </span>
              </div>
            </div>
          </Link>
          <nav className="hidden sm:flex items-center gap-6 text-sm">
            <a
              href="#features"
              className="text-neutral-300 hover:text-white transition-colors"
            >
              Features
            </a>
            <a
              href="#how"
              className="text-neutral-300 hover:text-white transition-colors"
            >
              How it works
            </a>
          </nav>
          <Link href="/interview">
            <Button className="hidden sm:inline-flex items-center gap-2 px-3 py-2.5 rounded-lg border border-indigo-500/30 bg-indigo-600 hover:bg-indigo-500">
              <span className="text-sm font-medium">Get started</span>
            </Button>
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="relative">
        <div className="max-w-7xl mx-auto px-6 py-16 sm:py-20 md:py-24">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-full border border-white/10 bg-white/5 text-xs text-neutral-300">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Now supporting audio-only interviews
              </div>
              <h1 className="mt-4 text-4xl sm:text-5xl md:text-6xl tracking-tight font-semibold">
                Hire smarter with voice-first interviews
              </h1>
              <p className="mt-4 text-neutral-300 text-base sm:text-lg">
                Record responses, review timelines, and export results in one
                streamlined workflow — fast, fair, and flexible.
              </p>
              <div className="mt-6 flex flex-col sm:flex-row gap-3">
                <Link href="/interview">
                  <Button className="group inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg border border-indigo-500/30 bg-indigo-600 hover:bg-indigo-500 text-white transition-all hover:-translate-y-0.5">
                    <Mic className="h-5 w-5" />
                    <span className="text-sm font-medium">Start interview</span>
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </Button>
                </Link>
                <Link href="/results">
                  <Button className="inline-flex items-center justify-center gap-2 px-4 py-3 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 hover:border-white/20 text-white transition-all">
                    <ClipboardList className="h-5 w-5" />
                    <span className="text-sm">View results</span>
                  </Button>
                </Link>
              </div>

              <div className="mt-8 flex items-center gap-6 text-sm text-neutral-400">
                <div className="flex items-center gap-2">
                  <Shield className="h-4.5 w-4.5 text-emerald-300" />
                  Private by default
                </div>
                <div className="flex items-center gap-2">
                  <Timer className="h-4.5 w-4.5 text-indigo-300" />
                  Under 5 minutes setup
                </div>
              </div>
            </div>

            {/* Preview Card */}
            <div className="relative">
              <div className="absolute -inset-4 rounded-2xl bg-gradient-to-br from-indigo-500/20 via-fuchsia-500/10 to-emerald-500/20 blur-xl opacity-60" />
              <div className="relative rounded-2xl border border-white/10 bg-white/5 overflow-hidden">
                <div className="p-5 border-b border-white/10 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-md bg-indigo-600/20 border border-indigo-500/30 grid place-items-center">
                      <Mic className="h-5 w-5 text-indigo-400" />
                    </div>
                    <div>
                      <p className="text-sm text-neutral-300">Sample role</p>
                      <h3 className="text-lg tracking-tight font-semibold">
                        Interview preview
                      </h3>
                    </div>
                  </div>
                </div>

                <div className="p-5 space-y-4">
                  {/* Progress */}
                  <div className="h-1.5 bg-neutral-900 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-indigo-500 to-indigo-400 transition-all"
                      style={{ width: "72%" }}
                    />
                  </div>

                  {/* Items */}
                  <div className="space-y-3">
                    <div className="group rounded-lg border border-white/10 bg-neutral-950/60 p-4 hover:bg-neutral-950/40 transition-colors">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="inline-flex items-center gap-2">
                            <span className="px-2 py-1 rounded-full text-xs border border-white/10 bg-white/5 text-neutral-300">
                              Easy
                            </span>
                            <span className="text-xs text-neutral-500">
                              Submitted
                            </span>
                          </div>
                          <h4 className="mt-2 text-base md:text-lg tracking-tight font-semibold">
                            Tell us about your most recent project.
                          </h4>
                        </div>
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-white/10 bg-neutral-900 text-xs tabular-nums">
                          <Mic className="h-3.5 w-3.5" />
                          00:52
                        </span>
                      </div>
                    </div>

                    <div className="group rounded-lg border border-white/10 bg-neutral-950/60 p-4 hover:bg-neutral-950/40 transition-colors">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="inline-flex items-center gap-2">
                            <span className="px-2 py-1 rounded-full text-xs border border-white/10 bg-white/5 text-neutral-300">
                              Medium
                            </span>
                            <span className="text-xs text-neutral-500">
                              Recording
                            </span>
                          </div>
                          <h4 className="mt-2 text-base md:text-lg tracking-tight font-semibold">
                            How do you approach debugging complex issues?
                          </h4>
                        </div>
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-white/10 bg-neutral-900 text-xs tabular-nums">
                          <Timer className="h-3.5 w-3.5" />
                          01:12
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Controls */}
                  <div className="flex items-center justify-between pt-2">
                    <div className="flex items-center gap-2 text-xs text-neutral-400">
                      <Headphones className="h-4 w-4" />
                      Audio on
                    </div>
                    <div className="flex items-center gap-2">
                      <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-white/10 bg-white/5 hover:bg-white/10 transition-colors text-xs">
                        <UploadCloud className="h-3.5 w-3.5" />
                        Export
                      </button>
                      <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-indigo-500/30 bg-indigo-600 hover:bg-indigo-500 transition-colors text-xs">
                        <BarChart3 className="h-3.5 w-3.5" />
                        Preview
                      </button>
                    </div>
                  </div>
                </div>

                <div className="p-4 border-t border-white/10 bg-neutral-950/60 text-xs text-neutral-400">
                  Stored locally in your browser. Nothing is uploaded.
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Logos */}
      <section className="border-t border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-4 opacity-80">
            <div className="text-neutral-400 text-xs uppercase tracking-wider">
              Trusted by teams
            </div>
            <div className="h-6 w-px bg-white/10" />
            <div className="text-neutral-300 text-sm font-medium tracking-tight">
              ALPHA
            </div>
            <div className="text-neutral-300 text-sm font-medium tracking-tight">
              NOVA
            </div>
            <div className="text-neutral-300 text-sm font-medium tracking-tight">
              ECHO
            </div>
            <div className="text-neutral-300 text-sm font-medium tracking-tight">
              PULSE
            </div>
            <div className="text-neutral-300 text-sm font-medium tracking-tight">
              QUARK
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="max-w-7xl mx-auto px-6 py-16 md:py-20">
        <div className="max-w-2xl">
          <h2 className="text-3xl md:text-4xl tracking-tight font-semibold">
            Everything you need to screen faster
          </h2>
          <p className="mt-2 text-neutral-300">
            Modern capture and review tools with privacy built in.
          </p>
        </div>

        <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {[
            {
              icon: Mic,
              title: "Voice capture",
              description: "Clear recordings with instant playback for each response.",
              color: "indigo",
            },
            {
              icon: Shield,
              title: "Local-first privacy",
              description:
                "Data stays in the browser by default. Export only when you choose.",
              color: "emerald",
            },
            {
              icon: BarChart3,
              title: "Clean review UI",
              description: "Durations, questions, and playback at a glance.",
              color: "fuchsia",
            },
            {
              icon: Timer,
              title: "Timeboxed flow",
              description: "Keep answers focused. Configure durations per question.",
              color: "amber",
            },
            {
              icon: UploadCloud,
              title: "One-click export",
              description: "Download JSON or audio per question when you're ready.",
              color: "sky",
            },
            {
              icon: Sliders,
              title: "Customizable",
              description:
                "Adjust role, questions, and difficulty levels to fit your needs.",
              color: "rose",
            },
          ].map((feature, idx) => {
            const Icon = feature.icon;
            const colorMap: Record<string, string> = {
              indigo: "indigo-600/20 border-indigo-500/30 text-indigo-400",
              emerald: "emerald-600/20 border-emerald-500/30 text-emerald-400",
              fuchsia: "fuchsia-600/20 border-fuchsia-500/30 text-fuchsia-400",
              amber: "amber-600/20 border-amber-500/30 text-amber-300",
              sky: "sky-600/20 border-sky-500/30 text-sky-300",
              rose: "rose-600/20 border-rose-500/30 text-rose-300",
            };
            return (
              <div
                key={idx}
                className="group rounded-xl border border-white/10 bg-white/5 p-5 hover:bg-white/10 hover:border-white/20 transition-colors"
              >
                <div
                  className={`h-10 w-10 rounded-md bg-${feature.color}-600/20 border border-${feature.color}-500/30 grid place-items-center`}
                >
                  <Icon className={`h-5 w-5 ${colorMap[feature.color]}`} />
                </div>
                <h3 className="mt-4 text-lg tracking-tight font-semibold">
                  {feature.title}
                </h3>
                <p className="mt-1 text-sm text-neutral-400">
                  {feature.description}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="max-w-7xl mx-auto px-6 pb-16 md:pb-20">
        <div className="rounded-2xl border border-white/10 bg-white/5 overflow-hidden">
          <div className="p-6 sm:p-8 border-b border-white/10">
            <h2 className="text-2xl md:text-3xl tracking-tight font-semibold">
              How it works
            </h2>
            <p className="mt-2 text-neutral-300">Three steps to better screening.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 divide-y md:divide-y-0 md:divide-x divide-white/10">
            <div className="p-6 sm:p-8">
              <div className="flex items-center gap-3">
                <span className="h-8 w-8 grid place-items-center rounded-md border border-white/10 bg-white/5 text-sm text-neutral-300">
                  01
                </span>
                <h3 className="text-lg tracking-tight font-semibold">
                  Set up the role
                </h3>
              </div>
              <p className="mt-2 text-sm text-neutral-400">
                Define position, add questions, and set durations per question.
              </p>
              <div className="mt-4 inline-flex items-center gap-2 text-xs text-neutral-400">
                <Briefcase className="h-4 w-4" />
                Role, difficulty, timing
              </div>
            </div>

            <div className="p-6 sm:p-8">
              <div className="flex items-center gap-3">
                <span className="h-8 w-8 grid place-items-center rounded-md border border-white/10 bg-white/5 text-sm text-neutral-300">
                  02
                </span>
                <h3 className="text-lg tracking-tight font-semibold">
                  Record answers
                </h3>
              </div>
              <p className="mt-2 text-sm text-neutral-400">
                Candidates speak naturally. Audio is captured and stored locally.
              </p>
              <div className="mt-4 inline-flex items-center gap-2 text-xs text-neutral-400">
                <Headphones className="h-4 w-4" />
                Natural voice, zero friction
              </div>
            </div>

            <div className="p-6 sm:p-8">
              <div className="flex items-center gap-3">
                <span className="h-8 w-8 grid place-items-center rounded-md border border-white/10 bg-white/5 text-sm text-neutral-300">
                  03
                </span>
                <h3 className="text-lg tracking-tight font-semibold">
                  Review & export
                </h3>
              </div>
              <p className="mt-2 text-sm text-neutral-400">
                Replay answers, check durations, and export JSON or audio.
              </p>
              <div className="mt-4 inline-flex items-center gap-2 text-xs text-neutral-400">
                <ClipboardCheck className="h-4 w-4" />
                Consistent and shareable
              </div>
            </div>
          </div>

          <div className="p-6 sm:p-8 border-t border-white/10 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="text-sm text-neutral-400">Ready to try it?</div>
            <div className="flex items-center gap-3">
              <Link href="/interview">
                <Button className="inline-flex items-center gap-2 px-3 py-2.5 rounded-lg border border-indigo-500/30 bg-indigo-600 hover:bg-indigo-500 text-white transition-colors">
                  <Mic className="h-4 w-4" />
                  <span className="text-sm font-medium">Start interview</span>
                </Button>
              </Link>
              <Link href="/results">
                <Button className="inline-flex items-center gap-2 px-3 py-2.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 transition-colors">
                  <ClipboardList className="h-4 w-4" />
                  <span className="text-sm">View results</span>
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Testimonial / Visual */}
      <section className="max-w-7xl mx-auto px-6 pb-16 md:pb-24">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 rounded-2xl overflow-hidden border border-white/10 bg-white/5">
            <img
              src="https://images.unsplash.com/photo-1547082299-de196ea013d6?q=80&w=1640&auto=format&fit=crop"
              alt="Interview review interface"
              className="w-full h-64 sm:h-72 md:h-80 object-cover opacity-90"
            />
            <div className="p-5 border-t border-white/10">
              <h3 className="text-lg tracking-tight font-semibold">
                Designed for clarity
              </h3>
              <p className="text-sm text-neutral-400 mt-1">
                A streamlined review surface for faster, fairer decisions.
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-3">
                <img
                  className="h-10 w-10 rounded-full ring-1 ring-white/10"
                  src="https://images.unsplash.com/photo-1547425260-76bcadfb4f2c?q=80&w=400&auto=format&fit=crop"
                  alt="Customer"
                />
                <div>
                  <div className="text-sm font-semibold tracking-tight">
                    Taylor R.
                  </div>
                  <div className="text-xs text-neutral-400">Talent Lead</div>
                </div>
              </div>
              <blockquote className="mt-4 text-sm text-neutral-300">
                "We reduced screening time by 60% while improving candidate
                experience. The audio-first flow just works."
              </blockquote>
            </div>
            <div className="mt-6 text-xs text-neutral-500">
              No accounts, no uploads — candidates love the simplicity.
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto px-6 py-8 border-t border-white/10 text-sm text-neutral-500">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <p>
            © <span id="year">{new Date().getFullYear()}</span> VoxHire. All
            rights reserved.
          </p>
          <div className="flex items-center gap-6">
            <a href="#" className="hover:text-neutral-300 transition-colors">
              Terms
            </a>
            <a href="#" className="hover:text-neutral-300 transition-colors">
              Privacy
            </a>
            <a href="#" className="hover:text-neutral-300 transition-colors">
              Contact
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
