import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
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
  const sessionId = params.get("sessionId") || "";

  if (!sessionId) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-white bg-neutral-950">
        <h1 className="text-2xl font-bold mb-4">No Results to Display</h1>
        <p className="text-neutral-400 mb-6">Session ID not provided</p>
        <a href="/" className="px-6 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500">
          Back to Home
        </a>
      </div>
    );
  }

  return (
    <Results
      sessionId={sessionId}
      onBack={() => (window.location.href = "/")}
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
