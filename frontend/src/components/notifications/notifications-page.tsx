"use client";

import { useEffect, useRef, useState } from "react";
import type { NotificationItem } from "@/lib/opportunities/types";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { formatPostedAt } from "@/lib/format";

export function NotificationsPage() {
  const [token, setToken] = useState<string | null>(null);
  const [items, setItems] = useState<NotificationItem[]>([]);
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
        if (t) setItems(await api.listNotifications(t));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load notifications");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function markRead(id: string) {
    if (!token) return;
    try {
      await api.markNotificationRead(id, token);
      setItems((prev) => prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update notification");
    }
  }

  async function markAllRead() {
    if (!token) return;
    try {
      await api.markAllNotificationsRead(token);
      setItems((prev) => prev.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update notifications");
    }
  }

  const unread = items.filter((n) => !n.read_at).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Notifications"
        subtitle={unread > 0 ? `${unread} unread update${unread === 1 ? "" : "s"}.` : "You're all caught up."}
        actions={
          unread > 0 ? (
            <Button variant="outline" size="sm" onClick={markAllRead}>
              Mark all read
            </Button>
          ) : undefined
        }
      />

      {error && <Alert>{error}</Alert>}

      {loading ? (
        <div className="animate-pulse space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-20 rounded-2xl bg-slate-200/70 dark:bg-slate-800" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="p-10 text-center text-sm text-slate-500 dark:text-slate-400">
            No notifications yet. Job matches, application updates and resume tips will appear here.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map((n) => (
            <Card key={n.id} className={!n.read_at ? "border-indigo-200 dark:border-indigo-800" : undefined}>
              <CardContent className="flex items-start justify-between gap-4 p-5">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    {!n.read_at && <span className="h-2 w-2 shrink-0 rounded-full bg-indigo-600" aria-label="Unread" />}
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">{n.title}</p>
                  </div>
                  {n.body && (
                    <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{n.body}</p>
                  )}
                  <p className="mt-1 text-xs text-slate-400">{formatPostedAt(n.created_at, true)}</p>
                </div>
                {!n.read_at && (
                  <Button variant="ghost" size="sm" onClick={() => markRead(n.id)}>
                    Mark read
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
