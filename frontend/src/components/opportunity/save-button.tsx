"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { BookmarkIcon } from "@/components/ui/icons";
import { api } from "@/lib/api";

export function SaveButton({
  opportunityId,
  token,
  defaultSaved = false,
}: {
  opportunityId: string;
  token: string;
  defaultSaved?: boolean;
}) {
  const [saved, setSaved] = useState(defaultSaved);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function toggle() {
    setLoading(true);
    setError("");
    try {
      if (saved) {
        await api.unsaveOpportunity(opportunityId, token);
        setSaved(false);
      } else {
        await api.saveOpportunity(opportunityId, token);
        setSaved(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update saved job");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        variant={saved ? "secondary" : "outline"}
        size="sm"
        onClick={toggle}
        loading={loading}
        aria-pressed={saved}
        title={saved ? "Remove from saved" : "Save job"}
      >
        <BookmarkIcon className={`h-4 w-4 ${saved ? "fill-current" : ""}`} aria-hidden="true" />
        {saved ? "Saved" : "Save"}
      </Button>
      {error && <span className="text-xs text-red-600 dark:text-red-400">{error}</span>}
    </div>
  );
}