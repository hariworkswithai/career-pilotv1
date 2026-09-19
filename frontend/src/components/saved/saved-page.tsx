"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { OpportunityRecord } from "@/lib/opportunities/types";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { OpportunityCard } from "@/components/opportunity/opportunity-card";

export function SavedPage() {
  const [token, setToken] = useState<string | null>(null);
  const [items, setItems] = useState<OpportunityRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const loaded = useRef(false);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    void (async () => {
      try {
        const t = await getAccessToken();
        setToken(t);
        if (t) setItems(await api.listSaved(t));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load saved jobs");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader title="Saved jobs" subtitle="Roles you shortlisted. Saved expired roles stay here with their status." />

      {error && <Alert>{error}</Alert>}

      {loading ? (
        <div className="animate-pulse space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-28 rounded-2xl bg-slate-200/70 dark:bg-slate-800" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="p-10 text-center">
            <p className="text-sm text-slate-500 dark:text-slate-400">Jobs you save will appear here.</p>
            <Link href="/jobs" className="mt-4 inline-block">
              <Button size="sm">Browse jobs</Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {items.map((opp) => (
            <OpportunityCard key={opp.id} opportunity={opp} token={token} defaultSaved />
          ))}
        </div>
      )}
    </div>
  );
}
