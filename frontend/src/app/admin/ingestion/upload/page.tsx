// /admin/ingestion/upload — form to upload a PDF and enqueue an import job.

"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ingestionAPI } from "@/lib/api";
import { EXAM_LABEL } from "../labels";

function errorText(err: any): string {
  const data = err?.response?.data;
  if (typeof data?.detail === "string") return data.detail;
  if (data && typeof data === "object") {
    const first = Object.values(data).flat().find((v) => typeof v === "string");
    if (typeof first === "string") return first;
  }
  return err?.message || "unknown error";
}

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [exam, setExam] = useState("neet_pg");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setMsg(null);
    setFailed(false);
    try {
      const matRes: any = await ingestionAPI.uploadMaterial(file, { exam_hint: exam });
      const mat = matRes?.data;
      setMsg(`Uploaded sha16=${mat?.sha256_short}. Creating job…`);
      const jobRes: any = await ingestionAPI.createJob({
        material_sha16: mat?.sha256_short,
        parent_exam: exam,
        strategy: "auto-pr-only",
      });
      const job = jobRes?.data;
      setMsg(`Job #${job?.id} dispatched.`);
      if (job?.id) router.push(`/admin/ingestion/jobs/${job.id}`);
    } catch (err: any) {
      setFailed(true);
      setMsg(`Error: ${errorText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="p-4 sm:p-6 max-w-xl space-y-4">
      <div>
        <Link href="/admin/ingestion" className="text-sm text-muted-foreground hover:text-foreground">
          ← Ingestion
        </Link>
        <h1 className="mt-1 text-2xl font-bold">Upload Material</h1>
      </div>
      <form onSubmit={onSubmit} className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium">PDF file</span>
          {/* Tailwind's preflight strips the native file button; style it so it reads as a button. */}
          <input
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="mt-1 block w-full text-sm text-muted-foreground file:mr-3 file:cursor-pointer file:rounded-md file:border file:border-solid file:border-border file:bg-muted file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-foreground hover:file:bg-muted/80"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Exam</span>
          <select
            value={exam}
            onChange={(e) => setExam(e.target.value)}
            className="block mt-1 rounded border border-border bg-background px-2 py-1"
          >
            {Object.entries(EXAM_LABEL).map(([code, label]) => (
              <option key={code} value={code}>{label}</option>
            ))}
          </select>
        </label>
        <div className="space-y-1">
          <button
            type="submit"
            disabled={!file || busy}
            className="rounded bg-primary text-primary-foreground px-4 py-2 disabled:opacity-50"
          >
            {busy ? "Uploading…" : "Upload & Dispatch"}
          </button>
          {!file && <p className="text-xs text-muted-foreground">Choose a PDF to enable upload.</p>}
        </div>
      </form>
      {msg && (
        <p className={`text-sm ${failed ? "text-destructive" : ""}`} role={failed ? "alert" : "status"}>
          {msg}
        </p>
      )}
    </div>
  );
}
