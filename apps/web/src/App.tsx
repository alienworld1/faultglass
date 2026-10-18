import { lazy, Suspense } from "react";
import { Link, Route, Routes } from "react-router-dom";
import CaseIntake from "./investigations/CaseIntake";
import MissingInvestigation from "./investigations/MissingInvestigation";
import ShowcasePage from "./showcase/ShowcasePage";
import LocalSetup from "./showcase/LocalSetup";

const SavedInvestigation = lazy(
  () => import("./investigations/SavedInvestigation"),
);

export default function App() {
  const showcase = import.meta.env.MODE === "showcase";
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
        <nav
          aria-label="Main navigation"
          className="flex items-center gap-5 text-sm"
        >
          <Link
            to="/run-locally"
            className="inline-flex min-h-11 items-center underline"
          >
            Run locally
          </Link>
          <a
            href="https://github.com/alienworld1/faultglass"
            className="inline-flex min-h-11 items-center underline"
          >
            Source code
          </a>
        </nav>
      </header>
      <main id="main-content" tabIndex={-1} className="min-w-0">
        <Routes>
          <Route
            path="/"
            element={showcase ? <ShowcasePage /> : <CaseIntake />}
          />
          <Route path="/run-locally" element={<LocalSetup />} />
          <Route
            path="/investigations/:id"
            element={
              showcase ? (
                <LocalSetup />
              ) : (
                <Suspense
                  fallback={
                    <p className="py-8" role="status">
                      Loading saved evidence…
                    </p>
                  }
                >
                  <SavedInvestigation />
                </Suspense>
              )
            }
          />
          <Route path="*" element={<MissingInvestigation />} />
        </Routes>
      </main>
    </div>
  );
}
