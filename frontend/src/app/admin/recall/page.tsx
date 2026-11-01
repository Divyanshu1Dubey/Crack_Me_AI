"use client";
/**
 * /admin/recall — Phase-3 admin status overview.
 * Aggregates QuestionImportJob + RecallSource + DuplicateCluster.
 *
 * The three lists load independently (Promise.allSettled): one failing
 * endpoint (a 500 on import jobs, a 429 from the question-bank limiter) shows
 * an error in its own section instead of replacing the whole page with a raw
 * axios message. Colours use the theme tokens so the page reads in light mode.
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import api from "@/lib/api";
import { listRows, loadErrorMessage } from "../_lib/adminHelpers";

interface ImportJob {
  id: number;
  status: string;
  source_filename?: string;
  created_at?: string;
  updated_at?: string;
  summary?: any;
}

interface Cluster { id: number; canonical_question_id: number; detection_method: string; member_count?: number; created_at?: string }

type SectionKey = "jobs" | "sources" | "clusters";

const SECTION_CLASS = "rounded-lg border border-border bg-card p-4";
const HEADING_CLASS = "mb-2 text-sm uppercase tracking-wider text-muted-foreground";
const TABLE_CLASS = "w-full text-sm [&_td]:py-1 [&_td]:pr-3 [&_th]:pr-3 [&_th]:font-semibold";
const THEAD_CLASS = "text-left text-xs uppercase text-muted-foreground";
const ROW_CLASS = "border-t border-border";

function SectionError({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-2xl border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
      {message}
    </div>
  );
}

function EmptyRow({ colSpan, text }: { colSpan: number; text: string }) {
  return (
    <tr className={ROW_CLASS}>
      <td colSpan={colSpan} className="text-muted-foreground">{text}</td>
    </tr>
  );
}

export default function AdminRecallPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  // Client-side admin gate, same as the other admin pages (the backend is
  // the authoritative RBAC; this keeps non-admins from loading the page).
  const isAdmin = !!user && (user.role === "admin" || user.is_admin);

  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const [images, setImages] = useState<any[]>([]);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [errs, setErrs] = useState<Partial<Record<SectionKey, string>>>({});
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace("/login?next=" + encodeURIComponent("/admin/recall"));
      return;
    }
    if (!isAdmin) {
      router.replace("/dashboard");
      return;
    }
    let alive = true;
    (async () => {
      const [j, im, cl] = await Promise.allSettled([
        api.get("/imports/neetpg/jobs/"),
        api.get("/questions/recall_sources/"),
        api.get("/questions/duplicate_clusters/"),
      ]);
      if (!alive) return;
      const nextErrs: Partial<Record<SectionKey, string>> = {};
      if (j.status === "fulfilled") setJobs(listRows<ImportJob>(j.value.data));
      else nextErrs.jobs = loadErrorMessage(j.reason, "import jobs");
      if (im.status === "fulfilled") setImages(listRows<any>(im.value.data));
      else nextErrs.sources = loadErrorMessage(im.reason, "recall sources");
      if (cl.status === "fulfilled") setClusters(listRows<Cluster>(cl.value.data));
      else nextErrs.clusters = loadErrorMessage(cl.reason, "duplicate clusters");
      setErrs(nextErrs);
      setLoading(false);
    })();
    return () => { alive = false; };
  }, [authLoading, user, isAdmin, router, reloadKey]);

  const reload = () => {
    setLoading(true);
    setReloadKey((k) => k + 1);
  };

  if (authLoading || !user) {
    return <p className="p-6 text-muted-foreground">Checking admin access…</p>;
  }
  if (!isAdmin) return null;

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-4 text-foreground sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Recall admin</h1>
        <button
          type="button"
          onClick={reload}
          disabled={loading}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium hover:bg-muted disabled:opacity-50"
        >
          {loading ? "Loading…" : Object.keys(errs).length > 0 ? "Retry" : "Refresh"}
        </button>
      </div>

      <section className={SECTION_CLASS}>
        <h2 className={HEADING_CLASS}>Import status</h2>
        {errs.jobs ? (
          <SectionError message={errs.jobs} />
        ) : (
          <div className="overflow-x-auto">
            <table className={TABLE_CLASS}>
              <thead className={THEAD_CLASS}>
                <tr><th>id</th><th>status</th><th>source</th><th>created</th><th>summary</th></tr>
              </thead>
              <tbody>
                {!loading && jobs.length === 0 && <EmptyRow colSpan={5} text="No import jobs yet." />}
                {jobs.slice(0, 20).map((j) => {
                  const summary = j.summary ? JSON.stringify(j.summary) : "";
                  return (
                    <tr key={j.id} className={ROW_CLASS}>
                      <td>{j.id}</td>
                      <td>{j.status}</td>
                      <td className="whitespace-nowrap">{j.source_filename || ""}</td>
                      <td className="whitespace-nowrap">{j.created_at?.slice(0, 16) || ""}</td>
                      <td className="text-xs text-muted-foreground">
                        <div className="max-w-xs truncate" title={summary}>{summary}</div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className={SECTION_CLASS}>
        <h2 className={HEADING_CLASS}>Recall sources (recent)</h2>
        {errs.sources ? (
          <SectionError message={errs.sources} />
        ) : (
          <div className="overflow-x-auto">
            <table className={TABLE_CLASS}>
              <thead className={THEAD_CLASS}>
                <tr><th>id</th><th>filename</th><th>sha16</th><th>scan_type</th><th>recall_status</th><th>created</th></tr>
              </thead>
              <tbody>
                {!loading && images.length === 0 && <EmptyRow colSpan={6} text="No recall sources yet." />}
                {images.slice(0, 20).map((s) => (
                  <tr key={s.id} className={ROW_CLASS}>
                    <td>{s.id}</td>
                    <td className="font-mono text-xs">{s.pdf_filename}</td>
                    <td className="font-mono text-xs">{s.pdf_sha256_short}</td>
                    <td>{s.scan_type}</td>
                    <td>{s.recall_status}</td>
                    <td className="whitespace-nowrap">{s.created_at?.slice(0, 16)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className={SECTION_CLASS}>
        <h2 className={HEADING_CLASS}>Duplicate clusters</h2>
        {errs.clusters ? (
          <SectionError message={errs.clusters} />
        ) : (
          <div className="overflow-x-auto">
            <table className={TABLE_CLASS}>
              <thead className={THEAD_CLASS}>
                <tr><th>id</th><th>canonical</th><th>method</th><th>members</th><th>created</th></tr>
              </thead>
              <tbody>
                {!loading && clusters.length === 0 && <EmptyRow colSpan={5} text="No duplicate clusters." />}
                {clusters.slice(0, 20).map((c) => (
                  <tr key={c.id} className={ROW_CLASS}>
                    <td>{c.id}</td>
                    <td>{c.canonical_question_id}</td>
                    <td>{c.detection_method}</td>
                    <td>{c.member_count ?? "—"}</td>
                    <td className="whitespace-nowrap">{c.created_at?.slice(0, 16)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
