import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router-dom";
import CaseIntake from "./investigations/CaseIntake";
import MissingInvestigation from "./investigations/MissingInvestigation";

const SavedInvestigation = lazy(
  () => import("./investigations/SavedInvestigation"),
);

export default function App() {
  return (
    <div className="mx-auto min-h-dvh w-full max-w-[1600px] min-w-0 px-4 sm:px-8">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-4 focus:z-50 focus:bg-surface focus:p-3"
      >
        Skip to content
      </a>
      <header className="flex h-13 items-center justify-between border-b border-line">
        <Link
          to="/"
          className="inline-flex min-h-11 items-center text-lg font-semibold"
        >
          FaultGlass
        </Link>
        <span className="text-sm text-muted">FalkorDB evidence workspace</span>
      </header>
      <main id="main-content" tabIndex={-1} className="min-w-0">
        <Routes>
          <Route path="/" element={<CaseIntake />} />
          <Route
            path="/investigations/:id"
            element={
              <Suspense
                fallback={
                  <p className="py-8" role="status">
                    Loading saved evidence…
                  </p>
                }
              >
                <SavedInvestigation />
              </Suspense>
            }
          />
          <Route path="*" element={<MissingInvestigation />} />
        </Routes>
      </main>
    </div>
  );
}
