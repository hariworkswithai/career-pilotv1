"use client";

import { useEffect, useRef, useState } from "react";
import type { RecommendationItem } from "@/lib/opportunities/types";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { MatchBadge } from "@/components/match/match-badge";
import { OpportunityCard } from "@/components/opportunity/opportunity-card";

export function RecommendedPage() {
  const [token, setToken] = useState<string | null>(null);
  const [items, setItems] = useState<RecommendationItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const loaded = useRef(false);
  const pageSize = 10;

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    void (async () => {
      try {
        const t = await getAccessToken();
        setToken(t);
        if (t) {
          const list = await api.listRecommendations({ page: 1, pageSize }, t);
          setItems(list.items);
          setTotal(list.total);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load recommendations");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function go(nextPage: number) {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const list = await api.listRecommendations({ page: nextPage, pageSize }, token);
      setItems(list.items);
      setTotal(list.total);
      setPage(nextPage);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load recommendations");
    } finally {
      setLoading(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Recommended for you"
        subtitle="Ranked by hard-filter eligibility, deterministic match score, then freshness."
      />

      {error && <Alert>{error}</Alert>}

      {loading && items.length === 0 ? (
        <div className="animate-pulse space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-28 rounded-2xl bg-slate-200/70 dark:bg-slate-800" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="p-10 text-center text-sm text-slate-500 dark:text-slate-400">
            We couldn&apos;t find strong matches right now. Try broadening your preferences.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {items.map(({ opportunity, match }) => (
            <div key={opportunity.id} className="relative">
              <div className="absolute right-3 top-3 z-10">
                <MatchBadge score={match.score} size="sm" />
              </div>
              <OpportunityCard opportunity={opportunity} token={token} />
            </div>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <Button variant="outline" size="sm" disabled={page <= 1 || loading} onClick={() => go(page - 1)}>
            Previous
          </Button>
          <span className="text-sm text-slate-500">
            Page {page} of {totalPages}
          </span>
          <Button variant="outline" size="sm" disabled={page >= totalPages || loading} onClick={() => go(page + 1)}>
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
