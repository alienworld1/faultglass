import { useCallback, useEffect, useState } from "react";
import CaseIntake from "./investigations/CaseIntake";
import InvestigationPage from "./investigations/InvestigationPage";

function App() {
  const [path, setPath] = useState(window.location.pathname);
  const navigate = useCallback((next: string) => {
    window.history.pushState(null, "", next);
    setPath(next);
  }, []);
  useEffect(() => {
    const change = () => setPath(window.location.pathname);
    window.addEventListener("popstate", change);
    return () => window.removeEventListener("popstate", change);
  }, []);
  const match = /^\/investigations\/([a-f0-9-]{36})$/.exec(path);
  return (
    <main className="mx-auto min-h-dvh max-w-5xl min-w-0 px-5 py-8 sm:px-12 sm:py-12">
      <header className="border-b border-line pb-6">
        <a
          href="/"
          className="text-xl font-semibold text-ink"
          onClick={(event) => {
            if (!event.ctrlKey && !event.metaKey) {
              event.preventDefault();
              navigate("/");
            }
          }}
        >
          FaultGlass
        </a>
        <p className="mt-3 text-base leading-relaxed text-muted">
          Compare reproducible cases across FalkorDB engines.
        </p>
        {path !== "/" ? (
          <a
            href="/"
            className="mt-4 inline-flex min-h-11 items-center underline"
            onClick={(event) => {
              event.preventDefault();
              sessionStorage.removeItem("faultglass.admission.v1");
              navigate("/");
            }}
          >
            New investigation
          </a>
        ) : null}
      </header>
      {path === "/" ? (
        <CaseIntake navigate={navigate} />
      ) : match ? (
        <InvestigationPage key={match[1]} id={match[1]} />
      ) : (
        <p className="py-8">We couldn’t find that investigation.</p>
      )}
    </main>
  );
}
export default App;
