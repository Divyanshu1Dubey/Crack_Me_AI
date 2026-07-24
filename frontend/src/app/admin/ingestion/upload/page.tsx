// /admin/ingestion/upload — drag-drop + form to enqueue a PDF.

"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ingestionAPI } from "@/lib/api";

export default function UploadPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [exam, setExam] = useState("neet_pg");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setMsg(null);
    try {
      const mat: any = await ingestionAPI.uploadMaterial(file, { exam_hint: exam });
      setMsg(`Uploaded sha16=${mat.sha256_short}. Creating job…`);
      const job: any = await ingestionAPI.createJob({
        material_sha16: mat.sha256_short,
        parent_exam: exam,
        strategy: "auto-pr-only",
      });
      setMsg(`Job #${job.id} dispatched.`);
      router.push(`/admin/ingestion/jobs/${job.id}`);
    } catch (err: any) {
      setMsg(`Error: ${err?.message || "unknown"}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="p-6 max-w-xl space-y-4">
      <h1 className="text-2xl font-bold">Upload Material</h1>
      <form onSubmit={onSubmit} className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium">PDF file</span>
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="block mt-1"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Exam</span>
          <select
            value={exam}
            onChange={(e) => setExam(e.target.value)}
            className="block mt-1 border rounded px-2 py-1"
          >
            <option value="neet_pg">NEET PG</option>
            <option value="ini_cet">INI-CET</option>
            <option value="fmge">FMGE</option>
            <option value="usmle">USMLE</option>
            <option value="plab">PLAB</option>
          </select>
        </label>
        <button
          type="submit"
          disabled={!file || busy}
          className="rounded bg-primary text-primary-foreground px-4 py-2 disabled:opacity-50"
        >
          {busy ? "Uploading…" : "Upload & Dispatch"}
        </button>
      </form>
      {msg && <p className="text-sm">{msg}</p>}
    </div>
  );
}
