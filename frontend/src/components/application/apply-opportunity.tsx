"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { OpportunityRecord } from "@/lib/opportunities/types";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { locationLabel } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Alert } from "@/components/ui/alert";
import { CheckCircleIcon, ExternalLinkIcon } from "@/components/ui/icons";
import { Button as SmallButton } from "@/components/ui/button";

export function ApplyOpportunity({ id }: { id: string }) {
  const [token, setToken] = useState<string | null>(null);
  const [opportunity, setOpportunity] = useState<OpportunityRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const loadedToken = useRef(false);

  useEffect(() => {
    if (!loadedToken.current) {
      loadedToken.current = true;
      void api
        .getOpportunity(id)
        .then(setOpportunity)
        .catch((e) => setError(e instanceof Error ? e.message : "Not found"))
        .finally(() => setLoading(false));
      getAccessToken().then(setToken).catch(() => setToken(null));
    }
  }, [id]);

  async function handleStart() {
    if (!token) {
      setError("You must be signed in to apply.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const application = await api.startApplication(id, token);
      setApplicationId(application.id);
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start application");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading && !opportunity) {
    return <div className="animate-pulse h-48 w-full bg-slate-100 dark:bg-slate-800 rounded-xl" />;
  }

  if (error && !opportunity) {
    return (
      <Card>
        <CardContent className="p-8 text-center text-sm text-red-600">{error}</CardContent>
      </Card>
    );
  }

  if (!opportunity) return null;

  const backLink = opportunity.is_internship ? "/internships" : "/jobs";

  return (
    <div className="space-y-6">
      <Link href={`${backLink}/${opportunity.id}`} className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline">
        ← Back to {opportunity.title}
      </Link>

      <PageHeader
        title={`Apply to ${opportunity.title}`}
        subtitle={`${opportunity.company_name} · ${locationLabel(opportunity.location)}`}
      />

      {done ? (
        <Card>
          <CardContent className="p-8 text-center">
            <CheckCircleIcon className="h-12 w-12 text-emerald-500 mx-auto mb-4" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Application started</h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              We tracked this application in your dashboard.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              {opportunity.apply_url && (
                <a
                  href={opportunity.apply_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-6 py-3 text-base font-medium text-white hover:bg-indigo-700"
                >
                  Complete on employer site <ExternalLinkIcon className="h-5 w-5" aria-hidden="true" />
                </a>
              )}
              <Link href="/applications">
                <SmallButton variant="outline" size="lg">
                  View applications
                </SmallButton>
              </Link>
              {applicationId && (
                <SmallButton
                  variant="secondary"
                  size="lg"
                  onClick={async () => {
                    try {
                      await api.updateApplication(applicationId, { status: "applied" }, token!);
                    } catch {
                      /* best effort */
                    }
                  }}
                >
                  Mark as applied
                </SmallButton>
              )}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-6 space-y-4">
            <p className="text-sm text-slate-600 dark:text-slate-400">
              CareerPilot will create a tracked application for this role. Because this posting lives on the
              employer&apos;s ATS, you&apos;ll continue on their site to submit. A future CareerPilot-assisted ATS
              flow will draft answers for you here.
            </p>
            {error && <Alert>{error}</Alert>}
            <div className="flex flex-wrap gap-3">
              <Button size="lg" onClick={handleStart} loading={submitting}>
                Confirm and start application
              </Button>
              <Link href={`${backLink}/${opportunity.id}`}>
                <Button variant="outline" size="lg">
                  Cancel
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}