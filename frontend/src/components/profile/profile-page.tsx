"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import type { Profile } from "@/lib/opportunities/types";
import { Card, CardContent } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export function ProfilePage() {
  const [token, setToken] = useState<string | null>(null);
  const [profile, setProfile] = useState<Partial<Profile> | null>(null);
  const [skills, setSkills] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const loaded = useRef(false);

  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    void (async () => {
      try {
        const t = await getAccessToken();
        setToken(t);
        if (t) {
          const p = await api.getProfile(t);
          setProfile(p);
          setSkills(p.skills.join(", "));
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not load profile");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const updated = await api.updateProfile(
        {
          ...profile,
          skills: skills
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        },
        token
      );
      setProfile(updated);
      setSuccess("Profile saved. Your matches will update immediately.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save profile");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Profile"
        subtitle="This powers your match scores. Keep it current."
      />

      {error && <Alert>{error}</Alert>}
      {success && <Alert tone="success">{success}</Alert>}

      {loading ? (
        <div className="animate-pulse h-64 w-full bg-slate-100 dark:bg-slate-800 rounded-xl" />
      ) : (
        <Card>
          <CardContent className="p-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="Full name"
                value={profile?.full_name ?? ""}
                onChange={(e) => setProfile((p) => ({ ...p, full_name: e.target.value }))}
                placeholder="Your name"
              />
              <Input
                label="Headline"
                value={profile?.headline ?? ""}
                onChange={(e) => setProfile((p) => ({ ...p, headline: e.target.value }))}
                placeholder="e.g. Frontend Engineer specialising in React & TypeScript"
                helperText="Used for role matching."
              />
              <div className="grid sm:grid-cols-2 gap-4">
                <Input
                  label="City"
                  value={profile?.city ?? ""}
                  onChange={(e) => setProfile((p) => ({ ...p, city: e.target.value }))}
                  placeholder="Bengaluru"
                />
                <Input
                  label="State"
                  value={profile?.state ?? ""}
                  onChange={(e) => setProfile((p) => ({ ...p, state: e.target.value }))}
                  placeholder="Karnataka"
                />
              </div>
              <div>
                <Label htmlFor="skills">Skills</Label>
                <Textarea
                  id="skills"
                  value={skills}
                  onChange={(e) => setSkills(e.target.value)}
                  placeholder="Python, Django, PostgreSQL"
                  helperText="Comma-separated. Core skills are weighted in the match score."
                  rows={3}
                />
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Completeness: {profile?.resume_completeness ?? 0}%
                </p>
                <Button type="submit" loading={saving}>
                  Save profile
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  );
}