// /admin/import-center/upload — drag/drop + multi-file + folder upload UI.
//
// Submitting a batch uploads files to /api/admin/import/upload/ which
// returns the new batch_id; we then poll /api/admin/import/batches/{id}/
// for live progress and redirect to the batch detail page when finished.

'use client';

import { useCallback, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { importCenterAPI } from '@/lib/api';

const ACCEPT = '.docx,.pdf,.pptx,.txt,.md,.zip';
const MAX_BYTES = 200 * 1024 * 1024;

export default function UploadPage() {
  const router = useRouter();
  const [files, setFiles] = useState<File[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{ batch_id: number; rejected: string[]; too_big: string[] } | null>(null);
  const [sourceLabel, setSourceLabel] = useState('');
  const [useAi, setUseAi] = useState(false);
  const [force, setForce] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const onFiles = useCallback((incoming: FileList | File[]) => {
    const arr = Array.from(incoming);
    const valid: File[] = [];
    const rejected: string[] = [];
    for (const f of arr) {
      const ext = '.' + (f.name.split('.').pop() || '').toLowerCase();
      if (!ACCEPT.split(',').includes(ext)) {
        rejected.push(`${f.name}: unsupported type`);
        continue;
      }
      if (f.size > MAX_BYTES) {
        rejected.push(`${f.name}: ${(f.size / 1024 / 1024).toFixed(1)} MB exceeds limit`);
        continue;
      }
      valid.push(f);
    }
    setFiles((prev) => [...prev, ...valid]);
    if (rejected.length) setError(rejected.join('; '));
    else setError(null);
  }, []);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) onFiles(e.dataTransfer.files);
  };

  const submit = async () => {
    if (!files.length) return;
    setError(null);
    setSuccess(null);
    setUploading(true);
    setProgress(0);
    const fd = new FormData();
    files.forEach((f) => fd.append('files', f, f.name));
    if (sourceLabel) fd.append('source_label', sourceLabel);
    fd.append('use_ai', useAi ? '1' : '0');
    fd.append('force', force ? '1' : '0');
    try {
      const r = await importCenterAPI.upload(fd, (p) => setProgress(p));
      const d = r.data;
      setSuccess({ batch_id: d.batch_id, rejected: d.files_rejected || [], too_big: d.files_too_big || [] });
      setFiles([]);
      setProgress(100);
      // Redirect to the batch detail after a brief pause.
      setTimeout(() => router.push(`/admin/import-center/batches/${d.batch_id}`), 1500);
    } catch (e: any) {
      setError(e?.response?.data?.error || e?.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const removeFile = (i: number) => setFiles((prev) => prev.filter((_, idx) => idx !== i));

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-xl font-bold">Upload Material</h2>
        <p className="text-sm text-muted-foreground">
          Supported formats: DOCX, PDF, PPTX, TXT, MD, ZIP. Max 200 MB per file, 200 files per upload.
        </p>
      </section>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`rounded border-2 border-dashed p-8 text-center transition ${
          dragOver ? 'border-primary bg-primary/5' : 'border-border bg-card'
        }`}
      >
        <div className="text-4xl">📤</div>
        <p className="mt-2 font-medium">Drag &amp; drop files here</p>
        <p className="text-sm text-muted-foreground">or use the buttons below</p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="rounded bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            Choose Files
          </button>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => e.target.files && onFiles(e.target.files)}
        />
        {/* Hint for folder selection (Chromium-only via webkitdirectory) */}
        <input
          type="file"
          multiple
          // @ts-expect-error - non-standard but widely supported
          webkitdirectory=""
          directory=""
          className="hidden"
          id="folder-input"
          onChange={(e) => e.target.files && onFiles(e.target.files)}
        />
        <label
          htmlFor="folder-input"
          className="mt-2 inline-block cursor-pointer rounded border border-border px-4 py-2 text-sm font-medium hover:bg-accent"
        >
          Choose Folder
        </label>
      </div>

      {files.length > 0 && (
        <section className="rounded border border-border bg-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold">{files.length} file(s) selected</h3>
            <button
              type="button"
              onClick={() => setFiles([])}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Clear
            </button>
          </div>
          <ul className="max-h-60 space-y-1 overflow-y-auto text-sm">
            {files.map((f, i) => (
              <li key={i} className="flex items-center justify-between rounded border border-border bg-background px-3 py-1">
                <span className="truncate">{f.name}</span>
                <span className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span>{(f.size / 1024 / 1024).toFixed(2)} MB</span>
                  <button type="button" onClick={() => removeFile(i)} className="text-red-500 hover:text-red-700">
                    ✕
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded border border-border bg-card p-4">
        <h3 className="mb-3 font-semibold">Options</h3>
        <div className="space-y-3 text-sm">
          <label className="block">
            <span className="text-xs text-muted-foreground">Source label (optional)</span>
            <input
              type="text"
              value={sourceLabel}
              onChange={(e) => setSourceLabel(e.target.value)}
              placeholder="e.g. NEET PG 2024 Recall — Docx Set 3"
              maxLength={255}
              className="mt-1 block w-full rounded border border-border bg-background px-3 py-1.5"
            />
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} />
            <span>Use AI classifier (slower but smarter subject/topic inference)</span>
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
            <span>
              Force re-import <span className="text-xs text-muted-foreground">(bypass cross-batch duplicate detection)</span>
            </span>
          </label>
        </div>
      </section>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800">{error}</div>
      )}

      {uploading && (
        <section className="rounded border border-border bg-card p-4">
          <div className="mb-2 flex justify-between text-sm">
            <span>Uploading…</span>
            <span>{progress}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded bg-border">
            <div className="h-full bg-primary transition-all" style={{ width: `${progress}%` }} />
          </div>
        </section>
      )}

      {success && (
        <div className="rounded border border-green-300 bg-green-50 p-3 text-sm text-green-800">
          Batch #{success.batch_id} created.{' '}
          {success.rejected.length > 0 && (
            <span>{success.rejected.length} file(s) rejected. </span>
          )}
          Redirecting to detail page…
          <div className="mt-2">
            <Link href={`/admin/import-center/batches/${success.batch_id}`} className="font-medium underline">
              Go now
            </Link>
          </div>
        </div>
      )}

      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={submit}
          disabled={!files.length || uploading}
          className="rounded bg-primary px-6 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {uploading ? 'Uploading…' : 'Upload &amp; Parse'}
        </button>
      </div>
    </div>
  );
}