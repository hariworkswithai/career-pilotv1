import type { Metadata } from "next";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: {
    default: "CareerPilot India — Jobs for India",
    template: "%s | CareerPilot India",
  },
  description:
    "India-first job discovery: AI-matched jobs and internships from top tech companies, with ATS autofill and application tracking.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}