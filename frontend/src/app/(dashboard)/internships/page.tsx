import { OpportunityExplorer } from "@/components/opportunity/opportunity-explorer";

export const metadata = {
  title: "Internships",
};

export default function InternshipsPage() {
  return <OpportunityExplorer kind="internships" />;
}