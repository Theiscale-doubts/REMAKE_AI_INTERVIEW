import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { useState } from "react";
import { Route, Switch, Router, useSearch } from "wouter";
import { useHashLocation } from "wouter/use-hash-location";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import Home from "./pages/Home";
import VoxHireApp from "./pages/Interview";
import Results from "./pages/Results";
import Admin from "./pages/Admin";

function AppRouter() {
  return (
    <Switch>
      <Route path={"/"} component={Home} />
      <Route path={"/interview"} component={VoxHireApp} />
      <Route path={"/admin"} component={Admin} />
      <Route path={"/results/:sessionId"} component={ResultsPageWrapper} />
      <Route path={"/results"} component={ResultsDirectAccess} />
      <Route component={NotFound} />
    </Switch>
  );
}

function ResultsPageWrapper({ params }: { params: { sessionId: string } }) {
  return (
    <Results
      sessionId={params.sessionId}
      onBack={() => (window.location.href = "/")}
      name=""
      email=""
      photo={null}
      role=""
      totalQuestions={9}
    />
  );
}

function ResultsDirectAccess() {
  const search = useSearch();
  const params = new URLSearchParams(search);
  const [sessionId, setSessionId] = useState(params.get("sessionId") || "");
  const [submitted, setSubmitted] = useState(!!params.get("sessionId"));

  if (!submitted) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-txt-hi bg-ink font-display px-4">
        <div className="vh-card-raised w-full max-w-md p-9 animate-fade-up">
          <h1 className="text-2xl tracking-tight font-semibold mb-2 text-center">View interview results</h1>
          <p className="text-txt-mid mb-7 text-center text-sm leading-relaxed">
            Enter the session ID from your interview URL to view your report.
          </p>
          <div className="flex gap-2.5">
            <input
              type="text"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sessionId.trim() && setSubmitted(true)}
              placeholder="Paste your session ID here"
              className="vh-input flex-1 px-4 py-3 text-sm"
            />
            <button
              onClick={() => sessionId.trim() && setSubmitted(true)}
              className="vh-btn-primary px-5 py-3 text-sm"
            >
              View
            </button>
          </div>
          <div className="mt-6 text-center">
            <a href="/" className="text-sm text-txt-low hover:text-txt-mid transition-colors">
              Back to home
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <Results
      sessionId={sessionId.trim()}
      onBack={() => setSubmitted(false)}
      name=""
      email=""
      photo={null}
      role=""
      totalQuestions={9}
    />
  );
}

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider defaultTheme="dark">
        <TooltipProvider>
          <Toaster />
          <Router hook={useHashLocation}>
            <AppRouter />
          </Router>
        </TooltipProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
