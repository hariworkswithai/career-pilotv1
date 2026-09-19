import Link from "next/link";
import { ArrowRightIcon, BriefcaseIcon, SparklesIcon, CheckCircleIcon } from "@/components/ui/icons";
import { BrandMark } from "@/components/ui/brand-mark";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <BrandMark className="h-8 w-8" />
            <span className="text-xl font-bold tracking-tight text-slate-900">CareerPilot</span>
          </Link>
          <nav className="flex items-center gap-4">
            <Link href="/login" className="text-sm font-medium text-slate-600 hover:text-slate-900">
              Sign in
            </Link>
            <Link
              href="/signup"
              className="inline-flex items-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Get started
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="max-w-6xl mx-auto px-4 sm:px-6 py-20 text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-sm font-medium text-indigo-700 mb-6">
            <SparklesIcon className="h-4 w-4" />
            Built for India, first
          </div>
          <h1 className="text-4xl sm:text-6xl font-bold tracking-tight text-slate-900 max-w-3xl mx-auto">
            Find jobs in India before anyone else
          </h1>
          <p className="mt-4 text-lg text-slate-600 max-w-2xl mx-auto">
            CareerPilot aggregates jobs and internships from top companies, checks India
            eligibility, matches them to your skills, and autofills applications.
          </p>
          <div className="mt-8 flex items-center justify-center gap-4">
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-6 py-3 text-base font-medium text-white hover:bg-indigo-700"
            >
              Create free account <ArrowRightIcon className="h-5 w-5" />
            </Link>
            <Link
              href="/login"
              className="inline-flex items-center rounded-lg border border-slate-300 px-6 py-3 text-base font-medium text-slate-700 hover:bg-slate-50"
            >
              Sign in
            </Link>
          </div>
        </section>

        <section className="max-w-5xl mx-auto px-4 sm:px-6 pb-20">
          <div className="grid sm:grid-cols-3 gap-5">
            {[
              {
                icon: <BriefcaseIcon className="h-5 w-5" />,
                title: "India eligibility check",
                text: "Every role is screened for remote scope, sponsorship, and location so you never waste time on roles that exclude India.",
              },
              {
                icon: <SparklesIcon className="h-5 w-5" />,
                title: "Skill-matched discovery",
                text: "Your profile and resume power a per-role match score, highlighted skills, and gap analysis.",
              },
              {
                icon: <CheckCircleIcon className="h-5 w-5" />,
                title: "One-tap applications",
                text: "ATS applications are drafted from your profile with a review step before anything is submitted.",
              },
            ].map((feature) => (
              <div key={feature.title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-[0_1px_2px_rgba(16,24,40,0.06)]">
                <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-700">
                  {feature.icon}
                </div>
                <h2 className="text-lg font-semibold tracking-tight text-slate-900">{feature.title}</h2>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{feature.text}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 text-center text-sm text-slate-500">
          CareerPilot India — jobs & internships for the Indian market.
        </div>
      </footer>
    </div>
  );
}