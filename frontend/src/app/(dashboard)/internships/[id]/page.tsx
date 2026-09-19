import type { Metadata } from "next";
import { OpportunityDetail } from "@/components/opportunity/opportunity-detail";

export const metadata: Metadata = {
  title: "Internship details",
};

export default async function InternshipDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <OpportunityDetail id={id} />;
}