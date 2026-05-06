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

function AppRouter() {
  return (
    <Switch>
      <Route path={"/"} component={Home} />
      <Route path={"/interview"} component={VoxHireApp} />
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
      <div className="min-h-screen flex flex-col items-center justify-center text-white bg-neutral-950 px-4">
        <div className="w-full max-w-md">
          <h1 className="text-2xl font-bold mb-2 text-center">View Interview Results</h1>
          <p className="text-neutral-400 mb-6 text-center text-sm">
            Enter the Session ID from your interview URL to view your results.
          </p>
          <div className="flex gap-2">
            <input
              type="text"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sessionId.trim() && setSubmitted(true)}
              placeholder="Paste your Session ID here"
              className="flex-1 px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder-neutral-500 focus:outline-none focus:border-indigo-500"
            />
            <button
              onClick={() => sessionId.trim() && setSubmitted(true)}
              className="px-4 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors"
            >
              View
            </button>
          </div>
          <div className="mt-4 text-center">
            <a href="/" className="text-sm text-neutral-500 hover:text-neutral-300 transition-colors">
              Back to Home
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
