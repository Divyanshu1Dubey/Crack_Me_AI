"use client";
/**
 * ImageGallery
 * ------------
 * Phase-3 multi-image grid for a question.
 *
 * - Lazy-loads (via QuestionImageZoom's `loading="lazy"`).
 * - Each image is clickable for fullscreen + zoom.
 * - Shows modality + body_region chip and OCR caption.
 * - Falls back to the existing single `page_screenshot` if the
 *   QuestionImage list is empty.
 */
import { useEffect, useState } from "react";
import QuestionImageZoom from "./QuestionImageZoom";
import api from "@/lib/api";

interface ImageRow {
  id: number;
  file_url?: string | null;
  modality?: string;
  body_region?: string;
  caption?: string;
  ocr_text?: string;
  page_number?: number;
  image_index_in_page?: number;
  // Bug fix 2026-08-01: rows with role='explanation' are admin-uploaded
  // figures that belong next to the explanation text. They MUST NOT
  // appear in this stem-pane grid before the student attempts the
  // question. The `images` endpoint is admin-only so student responses
  // are empty arrays already, but we filter here as defence-in-depth
  // for any admin-context gallery renders.
  role?: 'primary' | 'option' | 'illustration' | 'explanation' | string;
}

interface Props {
  questionId: number;
  fallbackImage?: string | null;
  fallbackCaption?: string | null;
}

export default function ImageGallery({ questionId, fallbackImage, fallbackCaption }: Props) {
  const [images, setImages] = useState<ImageRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await api.get(`/questions/${questionId}/images/`);
        if (alive) setImages(r.data || []);
      } catch (e: any) {
        if (alive) setError(e?.message || "Failed to load images");
      }
    })();
    return () => { alive = false; };
  }, [questionId]);

  if (error) {
    return (
      <div className="rounded border border-rose-500/40 bg-rose-500/10 p-3 text-sm text-rose-700 dark:text-rose-200">
        Image gallery unavailable: {error}
      </div>
    );
  }

  if (images === null) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="h-48 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    );
  }

  if (images.length === 0 && !fallbackImage) {
    return (
      <div className="rounded border border-border bg-card p-3 text-sm text-muted-foreground">
        No images for this question.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {images.filter((img) => img.role !== 'explanation').map((img) => (
        <div key={img.id} className="rounded-lg border border-border bg-card p-2">
          <QuestionImageZoom src={img} alt={`Image ${img.image_index_in_page ?? ""}`} />
          <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
            <span>page {img.page_number ?? "?"}{img.image_index_in_page != null ? ` · #${img.image_index_in_page}` : ""}</span>
            {img.modality ? <span className="rounded bg-emerald-600/70 px-1.5 py-0.5 text-white">{img.modality}</span> : null}
          </div>
        </div>
      ))}
      {images.length === 0 && fallbackImage ? (
        <QuestionImageZoom
          src={{ file_url: fallbackImage, caption: fallbackCaption || "" }}
          alt="Question screenshot"
          priority
        />
      ) : null}
    </div>
  );
}
