"use client";
/**
 * QuestionImageZoom
 * -----------------
 * Phase-3 recall image viewer.
 *
 * Features:
 *  - Click → fullscreen (<dialog>) with pinch-zoom (touch) / wheel-zoom
 *    (mouse).  Pure CSS transforms + inline pointer handling; no
 *    external lib required, keeps bundle small.
 *  - Captions + modality chip + OCR overlay toggle.
 *  - Lazy loading via `next/image` (or fallback <img loading="lazy">).
 *  - Future-proof: data-`data-annotate-target` lets a Phase-4
 *    annotation layer bind directly.
 */
import { useCallback, useEffect, useRef, useState } from "react";

interface SourceImage {
  file_url?: string | null;
  width?: number;
  height?: number;
  modality?: string;
  modality_subtype?: string;
  caption?: string;
  caption_source?: string;
  ocr_text?: string;
  has_diagram?: boolean;
  has_table?: boolean;
  is_watermarked?: boolean;
  body_region?: string;
}

interface Props {
  src: SourceImage;
  alt?: string;
  priority?: boolean;
}

export default function QuestionImageZoom({ src, alt = "Recall image", priority = false }: Props) {
  const [open, setOpen] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [tx, setTx] = useState(0);
  const [ty, setTy] = useState(0);
  const [showOcr, setShowOcr] = useState(false);

  // useCallback must be called unconditionally — declare it before any
  // early return so React Hook order stays stable across renders.
  const reset = useCallback(() => { setZoom(1); setTx(0); setTy(0); }, []);

  const url = src.file_url || "";
  if (!url) return null;

  return (
    <figure className="relative inline-block w-full max-w-2xl">
      <button
        type="button"
        onClick={() => { reset(); setOpen(true); }}
        className="group block w-full overflow-hidden rounded-lg border border-slate-700/40 bg-slate-900/60"
        aria-label="Open image fullscreen"
        data-annotate-target="image"
        data-modality={src.modality}
        data-caption-source={src.caption_source}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={url}
          alt={alt}
          loading={priority ? "eager" : "lazy"}
          decoding="async"
          className="block h-auto max-h-[60vh] w-full object-contain transition group-hover:scale-[1.01]"
        />
        {src.modality ? (
          <span className="absolute left-2 top-2 rounded bg-emerald-600/80 px-2 py-0.5 text-xs text-white">
            {src.modality}{src.body_region ? ` · ${src.body_region}` : ""}
          </span>
        ) : null}
        {src.caption ? (
          <figcaption className="px-3 py-2 text-left text-sm text-slate-200">
            {src.caption}
          </figcaption>
        ) : null}
      </button>

      {open ? (
        <FullscreenPortal
          url={url}
          alt={alt}
          zoom={zoom}
          tx={tx}
          ty={ty}
          setZoom={setZoom}
          setTx={setTx}
          setTy={setTy}
          reset={reset}
          close={() => setOpen(false)}
          showOcr={showOcr}
          setShowOcr={setShowOcr}
          ocrText={src.ocr_text}
        />
      ) : null}
    </figure>
  );
}

function FullscreenPortal(props: {
  url: string;
  alt: string;
  zoom: number;
  tx: number;
  ty: number;
  setZoom: (n: number) => void;
  setTx: (n: number) => void;
  setTy: (n: number) => void;
  reset: () => void;
  close: () => void;
  showOcr: boolean;
  setShowOcr: (b: boolean) => void;
  ocrText?: string;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const lastDist = useRef<number | null>(null);

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.key === "Escape") props.close();
      if (e.key === "+") props.setZoom(Math.min(6, props.zoom + 0.25));
      if (e.key === "-") props.setZoom(Math.max(1, props.zoom - 0.25));
      if (e.key === "0") props.reset();
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [props]);

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const next = Math.max(1, Math.min(6, props.zoom + (e.deltaY < 0 ? 0.2 : -0.2)));
    props.setZoom(next);
  }, [props]);

  const onPointerDown = (a: React.PointerEvent, b: React.PointerEvent) => {
    if (a.pointerType === "touch") {
      const dx = a.clientX - b.clientX;
      const dy = a.clientY - b.clientY;
      lastDist.current = Math.hypot(dx, dy);
    }
  };
  const onPointerMove = (a: React.PointerEvent, b: React.PointerEvent) => {
    if (a.pointerType !== "touch" || !lastDist.current) return;
    const dx = a.clientX - b.clientX;
    const dy = a.clientY - b.clientY;
    const dist = Math.hypot(dx, dy);
    const factor = dist / lastDist.current;
    lastDist.current = dist;
    props.setZoom(Math.max(1, Math.min(6, props.zoom * factor)));
  };

  return (
    <div
      ref={ref}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur"
      onClick={(e) => { if (e.target === e.currentTarget) props.close(); }}
    >
      <div className="absolute right-4 top-4 flex gap-2 text-white">
        <button onClick={() => props.setZoom(Math.min(6, props.zoom + 0.25))}
          className="rounded bg-white/10 px-2 py-1 text-sm hover:bg-white/20">+</button>
        <button onClick={() => props.setZoom(Math.max(1, props.zoom - 0.25))}
          className="rounded bg-white/10 px-2 py-1 text-sm hover:bg-white/20">-</button>
        <button onClick={props.reset}
          className="rounded bg-white/10 px-2 py-1 text-sm hover:bg-white/20">Reset</button>
        {props.ocrText ? (
          <button onClick={() => props.setShowOcr(!props.showOcr)}
            className="rounded bg-emerald-600/80 px-2 py-1 text-sm text-white hover:bg-emerald-500/80">
            {props.showOcr ? "Hide OCR" : "Show OCR"}
          </button>
        ) : null}
        <button onClick={props.close}
          className="rounded bg-red-600/80 px-2 py-1 text-sm text-white hover:bg-red-500/80">Close</button>
      </div>
      <div
        className="max-h-[90vh] max-w-[95vw] overflow-hidden"
        onWheel={onWheel}
        style={{ touchAction: "none" }}
        onPointerDown={(e) => { if (e.pointerType === "touch") {/* pinch handled below */} }}
      >
        <div
          style={{
            transform: `translate(${props.tx}px, ${props.ty}px) scale(${props.zoom})`,
            transformOrigin: "center center",
            transition: "transform 60ms linear",
          }}
          onTouchStart={(e) => {
            if (e.touches.length === 2) {
              const [a, b] = [e.touches[0], e.touches[1]];
              onPointerDown({ ...a, pointerType: "touch" } as any, { ...b, pointerType: "touch" } as any);
            }
          }}
          onTouchMove={(e) => {
            if (e.touches.length === 2) {
              const [a, b] = [e.touches[0], e.touches[1]];
              onPointerMove({ ...a, pointerType: "touch" } as any, { ...b, pointerType: "touch" } as any);
            }
          }}
          onTouchEnd={() => { lastDist.current = null; }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={props.url} alt={props.alt}
            className="block max-h-[90vh] max-w-[95vw] object-contain" />
        </div>
        {props.showOcr && props.ocrText ? (
          <pre className="mt-3 max-h-[30vh] overflow-auto whitespace-pre-wrap rounded
                          bg-black/70 p-3 text-xs text-emerald-100">
            {props.ocrText}
          </pre>
        ) : null}
      </div>
    </div>
  );
}
