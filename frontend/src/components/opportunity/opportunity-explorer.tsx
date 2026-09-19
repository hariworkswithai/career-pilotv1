"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  MatchResult,
  OpportunityRecord,
  SuggestionItem,
  WorkplaceType,
} from "@/lib/opportunities/types";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { OpportunityCard } from "@/components/opportunity/opportunity-card";
import { MatchBadge } from "@/components/match/match-badge";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { PageHeader } from "@/components/ui/page-header";
import { Alert } from "@/components/ui/alert";
import { SearchIcon } from "@/components/ui/icons";

export function OpportunityExplorer({
  kind,
}: {
  kind: "jobs" | "internships";
}) {
  const [token, setToken] = useState<string | null>(null);
  const [items, setItems] = useState<OpportunityRecord[]>([]);
  const [matches, setMatches] = useState<Record<string, MatchResult>>({});
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [q, setQ] = useState("");
  const [qDraft, setQDraft] = useState("");
  const [cities, setCities] = useState<string[]>([]);
  const [cityDraft, setCityDraft] = useState("");
  const [citySuggestions, setCitySuggestions] = useState<SuggestionItem[]>([]);
  const [cityOpen, setCityOpen] = useState(false);
  const cityTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [workModes, setWorkModes] = useState<WorkplaceType[]>([]);
  const [postedDays, setPostedDays] = useState<number | undefined>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const mounted = useRef(true);

  const load = useCallback(
    async (
      args: {
        token: string | null;
        page: number;
        q: string;
        workModes: WorkplaceType[];
        postedDays?: number;
        cities: string[];
      }
    ) => {
      try {
        const filters = {
          q: args.q,
          work_modes: args.workModes,
          cities: args.cities,
          ...(args.postedDays ? { posted_days: args.postedDays } : {}),
        };
        const list =
          kind === "jobs"
            ? await api.listJobs(filters, args.page, pageSize)
            : await api.listInternships(filters, args.page, pageSize);
        if (!mounted.current) return;
        setItems(list.items);
        setTotal(list.total);

        const ids = list.items.map((o) => o.id);
        if (args.token && ids.length) {
          try {
            const results = await api.batchMatch(ids, args.token);
            if (!mounted.current) return;
            setMatches(
              Object.fromEntries(results.map((r) => [r.opportunity_id, r.match]))
            );
          } catch {
            setMatches({});
          }
        } else {
          setMatches({});
        }
      } catch (e) {
        if (!mounted.current) return;
        setError(e instanceof Error ? e.message : "Could not load opportunities");
        setItems([]);
        setTotal(0);
      } finally {
        if (mounted.current) setLoading(false);
      }
    },
    [kind, pageSize]
  );

  useEffect(() => {
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    getAccessToken()
      .then((t) => {
        if (!mounted.current) return;
        setToken(t);
        void load({ token: t, page: 1, q: "", workModes: [], postedDays: undefined, cities: [] });
      })
      .catch(() => {
        if (mounted.current)
          void load({ token: null, page: 1, q: "", workModes: [], postedDays: undefined, cities: [] });
      });
    return () => {
      mounted.current = false;
    };
  }, [load]);

  function runSearch(nextPage = 1) {
    setLoading(true);
    setError("");
    setPage(nextPage);
    void load({ token, page: nextPage, q, workModes, postedDays, cities });
  }

  function toggleWorkMode(mode: WorkplaceType) {
    const next = workModes.includes(mode)
      ? workModes.filter((m) => m !== mode)
      : [...workModes, mode];
    setWorkModes(next);
    setLoading(true);
    setError("");
    setPage(1);
    void load({ token, page: 1, q, workModes: next, postedDays, cities });
  }

  function changePostedDays(value: string) {
    const next = value ? Number(value) : undefined;
    setPostedDays(next);
    setLoading(true);
    setError("");
    setPage(1);
    void load({ token, page: 1, q, workModes, postedDays: next, cities });
  }

  function onCityDraftChange(value: string) {
    setCityDraft(value);
    if (cityTimer.current) clearTimeout(cityTimer.current);
    if (value.trim().length < 2) {
      setCitySuggestions([]);
      setCityOpen(false);
      return;
    }
    cityTimer.current = setTimeout(() => {
      api
        .suggestCities(value.trim())
        .then((items) => {
          if (!mounted.current) return;
          setCitySuggestions(items);
          setCityOpen(true);
        })
        .catch(() => {});
    }, 200);
  }

  function addCity(value: string) {
    if (!value || cities.includes(value)) {
      setCityDraft("");
      setCityOpen(false);
      return;
    }
    const next = [...cities, value];
    setCities(next);
    setCityDraft("");
    setCitySuggestions([]);
    setCityOpen(false);
    setLoading(true);
    setError("");
    setPage(1);
    void load({ token, page: 1, q, workModes, postedDays, cities: next });
  }

  function removeCity(value: string) {
    const next = cities.filter((c) => c !== value);
    setCities(next);
    setLoading(true);
    setError("");
    setPage(1);
    void load({ token, page: 1, q, workModes, postedDays, cities: next });
  }

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div>
      <PageHeader
        title={kind === "jobs" ? "Job Search" : "Internships in India"}
        subtitle={`Eligible roles screened for the Indian market. ${total} available.`}
      />

      <div className="mb-6 space-y-4 rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4 sm:p-5 shadow-[0_1px_2px_rgba(16,24,40,0.06)]">
        <form
          className="flex flex-col sm:flex-row gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            setQ(qDraft);
            setLoading(true);
            setError("");
            setPage(1);
            void load({ token, page: 1, q: qDraft, workModes, postedDays, cities });
          }}
        >
          <div className="relative flex-1">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              value={qDraft}
              onChange={(e) => setQDraft(e.target.value)}
              placeholder="Search role, company, skill…"
              className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <Button type="submit" loading={loading}>
            Search
          </Button>
        </form>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Work mode
          </span>
          {(["on_site", "hybrid", "remote"] as WorkplaceType[]).map((mode) => (
            <Chip
              key={mode}
              active={workModes.includes(mode)}
              onClick={() => toggleWorkMode(mode)}
            >
              {mode === "on_site" ? "On-site" : mode === "hybrid" ? "Hybrid" : "Remote"}
            </Chip>
          ))}
          <select
            value={postedDays ?? ""}
            onChange={(e) => changePostedDays(e.target.value)}
            className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-sm px-3 py-1.5 text-slate-700 dark:text-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">Any posted date</option>
            <option value="7">Last 7 days</option>
            <option value="14">Last 14 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
          </select>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            City
          </span>
          {cities.map((c) => (
            <Chip key={c} active onClick={() => removeCity(c)} aria-label={`Remove ${c} filter`}>
              {c} ✕
            </Chip>
          ))}
          <div className="relative">
            <input
              value={cityDraft}
              onChange={(e) => onCityDraftChange(e.target.value)}
              onFocus={() => citySuggestions.length > 0 && setCityOpen(true)}
              onBlur={() => setTimeout(() => setCityOpen(false), 150)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && citySuggestions.length > 0) {
                  e.preventDefault();
                  addCity(citySuggestions[0].value);
                }
                if (e.key === "Escape") setCityOpen(false);
              }}
              placeholder="Type a city…"
              role="combobox"
              aria-expanded={cityOpen}
              aria-controls="city-suggestions"
              aria-autocomplete="list"
              className="w-40 rounded-full border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs text-slate-700 dark:text-slate-300 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            {cityOpen && citySuggestions.length > 0 && (
              <ul
                id="city-suggestions"
                role="listbox"
                className="absolute left-0 top-full z-20 mt-1 w-48 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800"
              >
                {citySuggestions.map((s) => (
                  <li key={s.value} role="option" aria-selected={false}>
                    <button
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        addCity(s.value);
                      }}
                      className="block w-full px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
                    >
                      {s.label}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {error && <Alert>{error}</Alert>}

      {loading && items.length === 0 ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="animate-pulse rounded-xl border border-slate-200 dark:border-slate-700 p-5">
              <div className="h-4 w-1/2 bg-slate-200 dark:bg-slate-700 rounded mb-2" />
              <div className="h-3 w-1/3 bg-slate-200 dark:bg-slate-700 rounded mb-4" />
              <div className="h-3 w-full bg-slate-100 dark:bg-slate-800 rounded" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => (
            <div key={item.id} className="relative">
              {matches[item.id] && (
                <div className="absolute top-1 right-1 z-10">
                  <MatchBadge score={matches[item.id].score} size="sm" />
                </div>
              )}
              <OpportunityCard opportunity={item} token={token} />
            </div>
          ))}
          {items.length === 0 && !loading && (
            <div className="rounded-xl border border-dashed border-slate-300 dark:border-slate-700 p-10 text-center text-sm text-slate-500">
              No {kind === "jobs" ? "jobs" : "internships"} match your filters yet.
            </div>
          )}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-6">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1 || loading}
            onClick={() => runSearch(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-slate-500">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages || loading}
            onClick={() => runSearch(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}