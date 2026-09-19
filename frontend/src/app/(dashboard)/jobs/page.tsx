import { OpportunityExplorer } from "@/components/opportunity/opportunity-explorer";

export const metadata = {
  title: "Jobs",
};

export default function JobsPage() {
  return <OpportunityExplorer kind="jobs" />;
}