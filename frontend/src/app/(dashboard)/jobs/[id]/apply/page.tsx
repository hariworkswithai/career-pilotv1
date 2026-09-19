import type { Metadata } from "next";
import { ApplyOpportunity } from "@/components/application/apply-opportunity";

export const metadata: Metadata = {
  title: "Apply",
};

export default async function ApplyPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ApplyOpportunity id={id} />;
}