"use client";
/**
 * /admin/recall/search-analytics — Phase-3 admin placeholder.
 * Pulls the /api/analytics/search_analytics/ stub.  When Phase 4
 * instruments the front-end search box, this becomes a real
 * dashboard.
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import api from "@/lib/api";
import { loadErrorMessage } from "../../_lib/adminHelpers";

interface Row {
  top_queries: { query: string; count: number }[];
  daily: { date: string; n: number }[];
}

export default function SearchAnalyticsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  // Client-side admin gate, same as the other admin pages.
  const isAdmin = !!user && (user.role === "admin" || user.is_admin);
  const [d, setD] = useState<Row | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace("/login?next=" + encodeURIComponent("/admin/recall/search-analytics"));
      return;
    }
    if (!isAdmin) {
      router.replace("/dashboard");
      return;
    }
    let alive = true;
    (async () => {
      try {
        const r = await api.get("/analytics/search_analytics/");
        if (alive) setD(r.data);
      } catch (e: unknown) {
        if (alive) setErr(loadErrorMessage(e, "search analytics"));
      }
    })();
    return () => { alive = false; };
  }, [authLoading, user, isAdmin, router]);

  if (authLoading || !user) return <p className="p-6 text-muted-foreground">Checking admin access…</p>;
  if (!isAdmin) return null;
  if (err) {
    return (
      <main className="mx-auto max-w-4xl p-4 sm:p-6">
        <div role="alert" className="rounded-2xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
          {err}
        </div>
      </main>
    );
  }
  if (!d) return <p className="p-6 text-muted-foreground">Loading…</p>;

  const topQueries = Array.isArray(d.top_queries) ? d.top_queries : [];
  const daily = Array.isArray(d.daily) ? d.daily : [];

  return (
    <main className="mx-auto max-w-4xl space-y-4 p-4 text-foreground sm:p-6">
      <h1 className="text-2xl font-semibold">Search analytics</h1>
      <p className="text-sm text-muted-foreground">
        Top search terms and daily search volume. Search logging isn&apos;t switched on yet, so this page stays
        empty until it is.
      </p>
      <section className="rounded-lg border border-border bg-card p-3 text-sm">
        <h2 className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">Top queries</h2>
        {topQueries.length === 0 ? (
          <p className="text-muted-foreground">No searches recorded yet.</p>
        ) : (
          <ul>{topQueries.map((q) => <li key={q.query}>{q.query} — {q.count}</li>)}</ul>
        )}
      </section>
      <section className="rounded-lg border border-border bg-card p-3 text-sm">
        <h2 className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">Daily volume</h2>
        {daily.length === 0 ? (
          <p className="text-muted-foreground">No searches recorded yet.</p>
        ) : (
          <ul>{daily.map((row) => <li key={row.date}>{row.date}: {row.n}</li>)}</ul>
        )}
      </section>
    </main>
  );
}
