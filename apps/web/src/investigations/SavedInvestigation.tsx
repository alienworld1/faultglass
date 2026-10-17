import { useParams } from "react-router-dom";
import InvestigationPage from "./InvestigationPage";
import MissingInvestigation from "./MissingInvestigation";
export default function SavedInvestigation() {
  const { id = "" } = useParams();
  return /^[a-f0-9-]{36}$/.test(id) ? (
    <InvestigationPage key={id} id={id} />
  ) : (
    <MissingInvestigation />
  );
}
