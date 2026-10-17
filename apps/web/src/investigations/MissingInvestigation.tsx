import { Link } from "react-router-dom";
export default function MissingInvestigation() {
  return (
    <section className="py-8">
      <h1 className="text-2xl font-semibold">
        We couldn’t find that investigation.
      </h1>
      <Link to="/" className="mt-4 inline-flex min-h-11 items-center underline">
        New investigation
      </Link>
    </section>
  );
}
