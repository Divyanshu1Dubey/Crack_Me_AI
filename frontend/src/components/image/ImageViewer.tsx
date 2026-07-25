"use client";
/**
 * ImageViewer — Phase-7 full-screen image viewer.
 *
 * Features:
 *   - Zoom slider + buttons (50% / 100% / 150% / 200% / fit)
 *   - Drag-to-pan when zoomed in (mouse + touch)
 *   - Fullscreen toggle (uses the browser Fullscreen API)
 *   - Annotation overlay — renders caption + modality + page/index
 *     callouts when toggled on
 *   - Side-by-side mode — open multiple QuestionImage rows in a
 *     horizontal scroll gallery inside the same modal
 *   - Keyboard shortcuts: Esc (close), + / = (zoom in), - / _ (zoom
 *     out), 0 (reset), f (fullscreen), a (toggle annotations),
 *     ← / → (navigate when multiple images)
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
    X, ZoomIn, ZoomOut, Maximize2, Minimize2, Highlighter,
    ChevronLeft, ChevronRight, RotateCw, Columns2, ImageIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export interface ViewerImage {
    id: number;
    file_url: string | null;
    caption?: string | null;
    modality?: string | null;
    modality_subtype?: string | null;
    page_number?: number | null;
    image_index_in_page?: number | null;
    has_diagram?: boolean;
    has_table?: boolean;
    width?: number | null;
    height?: number | null;
}

interface ImageViewerProps {
    images: ViewerImage[];
    /** Which image was the user looking at when the viewer opened? */
    startIndex?: number;
    open: boolean;
    onClose: () => void;
}

const ZOOM_LEVELS = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3];
const DEFAULT_ZOOM = 1;

export default function ImageViewer({ images, startIndex = 0, open, onClose }: ImageViewerProps) {
    const [index, setIndex] = useState(startIndex);
    const [zoom, setZoom] = useState(DEFAULT_ZOOM);
    const [pos, setPos] = useState({ x: 0, y: 0 });
    const [annotationsOn, setAnnotationsOn] = useState(true);
    const [sideBySide, setSideBySide] = useState(false);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [rotate, setRotate] = useState(0);
    const [dragging, setDragging] = useState(false);

    const containerRef = useRef<HTMLDivElement | null>(null);
    const dragOriginRef = useRef<{ x: number; y: number; px: number; py: number } | null>(null);

    const current = images[index];

    // Reset state every time the viewer opens.
    useEffect(() => {
        if (open) {
            setIndex(Math.max(0, Math.min(images.length - 1, startIndex)));
            setZoom(DEFAULT_ZOOM);
            setPos({ x: 0, y: 0 });
            setRotate(0);
            setAnnotationsOn(true);
        }
    }, [open, startIndex, images.length]);

    // Body-scroll lock when the viewer is open.
    useEffect(() => {
        if (!open) return;
        const prev = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => { document.body.style.overflow = prev; };
    }, [open]);

    // Fullscreen API tracking.
    useEffect(() => {
        const onFs = () => setIsFullscreen(!!document.fullscreenElement);
        document.addEventListener("fullscreenchange", onFs);
        return () => document.removeEventListener("fullscreenchange", onFs);
    }, []);

    const requestFullscreen = useCallback(() => {
        const el = containerRef.current;
        if (!el) return;
        if (document.fullscreenElement) {
            document.exitFullscreen().catch(() => {});
        } else {
            el.requestFullscreen?.().catch(() => {});
        }
    }, []);

    const zoomBy = useCallback((delta: number) => {
        setZoom((z) => {
            const idx = ZOOM_LEVELS.findIndex((l) => Math.abs(l - z) < 0.01);
            const next = ZOOM_LEVELS[Math.max(0, Math.min(ZOOM_LEVELS.length - 1, (idx < 0 ? ZOOM_LEVELS.indexOf(1) : idx) + delta))];
            return next ?? z;
        });
    }, []);

    const resetView = useCallback(() => {
        setZoom(DEFAULT_ZOOM);
        setPos({ x: 0, y: 0 });
        setRotate(0);
    }, []);

    // Keyboard shortcuts.
    useEffect(() => {
        if (!open) return;
        const h = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
            else if (e.key === "+" || e.key === "=") zoomBy(+1);
            else if (e.key === "-" || e.key === "_") zoomBy(-1);
            else if (e.key === "0") resetView();
            else if (e.key === "f" || e.key === "F") requestFullscreen();
            else if (e.key === "a" || e.key === "A") setAnnotationsOn((v) => !v);
            else if (e.key === "r" || e.key === "R") setRotate((r) => (r + 90) % 360);
            else if (e.key === "s" || e.key === "S") setSideBySide((v) => !v);
            else if (e.key === "ArrowLeft") setIndex((i) => Math.max(0, i - 1));
            else if (e.key === "ArrowRight") setIndex((i) => Math.min(images.length - 1, i + 1));
        };
        window.addEventListener("keydown", h);
        return () => window.removeEventListener("keydown", h);
    }, [open, onClose, zoomBy, resetView, requestFullscreen, images.length]);

    // Drag-to-pan handlers.
    const onMouseDown = useCallback((e: React.MouseEvent) => {
        if (zoom <= 1) return;
        setDragging(true);
        dragOriginRef.current = { x: e.clientX, y: e.clientY, px: pos.x, py: pos.y };
    }, [zoom, pos]);

    const onMouseMove = useCallback((e: React.MouseEvent) => {
        if (!dragging || !dragOriginRef.current) return;
        const dx = e.clientX - dragOriginRef.current.x;
        const dy = e.clientY - dragOriginRef.current.y;
        setPos({ x: dragOriginRef.current.px + dx, y: dragOriginRef.current.py + dy });
    }, [dragging]);

    const onMouseUp = useCallback(() => {
        setDragging(false);
        dragOriginRef.current = null;
    }, []);

    const onWheel = useCallback((e: React.WheelEvent) => {
        if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            zoomBy(e.deltaY > 0 ? -1 : +1);
        }
    }, [zoomBy]);

    if (!open || !images.length) return null;

    return (
        <div
            className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm"
            role="dialog"
            aria-modal="true"
            aria-label="Image viewer"
            data-testid="image-viewer"
            ref={containerRef}
        >
            {/* Top bar */}
            <div className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-4 py-3 bg-gradient-to-b from-black/70 to-transparent">
                <div className="flex items-center gap-2 text-white text-sm font-medium">
                    <ImageIcon className="w-4 h-4" />
                    <span>
                        {sideBySide
                            ? `${images.length} images`
                            : `${index + 1} / ${images.length}`}
                    </span>
                    {current?.modality && current.modality !== 'other' ? (
                        <span className="ml-2 rounded bg-white/20 px-2 py-0.5 text-[11px] uppercase tracking-wide">
                            {current.modality}
                        </span>
                    ) : null}
                </div>
                <div className="flex items-center gap-1">
                    <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => zoomBy(-1)}
                        aria-label="Zoom out"
                        className="text-white hover:bg-white/20"
                        data-testid="iv-zoom-out"
                    >
                        <ZoomOut className="w-4 h-4" />
                    </Button>
                    <input
                        type="range"
                        min={0}
                        max={ZOOM_LEVELS.length - 1}
                        value={Math.max(0, ZOOM_LEVELS.indexOf(zoom))}
                        onChange={(e) => setZoom(ZOOM_LEVELS[Number(e.target.value)])}
                        className="w-32 accent-teal-400"
                        aria-label="Zoom level"
                        data-testid="iv-zoom-slider"
                    />
                    <span className="text-white text-xs w-12 text-center tabular-nums">{Math.round(zoom * 100)}%</span>
                    <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => zoomBy(+1)}
                        aria-label="Zoom in"
                        className="text-white hover:bg-white/20"
                        data-testid="iv-zoom-in"
                    >
                        <ZoomIn className="w-4 h-4" />
                    </Button>
                    <Button
                        size="icon"
                        variant="ghost"
                        onClick={resetView}
                        aria-label="Reset zoom"
                        className="text-white hover:bg-white/20"
                        title="Reset (0)"
                    >
                        <span className="text-xs">1×</span>
                    </Button>
                    <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => setRotate((r) => (r + 90) % 360)}
                        aria-label="Rotate"
                        className="text-white hover:bg-white/20"
                        title="Rotate (r)"
                    >
                        <RotateCw className="w-4 h-4" />
                    </Button>
                    <Button
                        size="icon"
                        variant={annotationsOn ? "default" : "ghost"}
                        onClick={() => setAnnotationsOn((v) => !v)}
                        aria-label="Toggle annotations"
                        className={cn("text-white hover:bg-white/20", annotationsOn && "bg-violet-600 hover:bg-violet-700")}
                        data-testid="iv-annotations"
                        title="Annotations (a)"
                    >
                        <Highlighter className="w-4 h-4" />
                    </Button>
                    <Button
                        size="icon"
                        variant={sideBySide ? "default" : "ghost"}
                        onClick={() => setSideBySide((v) => !v)}
                        aria-label="Side-by-side"
                        className={cn("text-white hover:bg-white/20", sideBySide && "bg-teal-600 hover:bg-teal-700")}
                        title="Side-by-side (s)"
                        data-testid="iv-side-by-side"
                    >
                        <Columns2 className="w-4 h-4" />
                    </Button>
                    <Button
                        size="icon"
                        variant="ghost"
                        onClick={requestFullscreen}
                        aria-label="Toggle fullscreen"
                        className="text-white hover:bg-white/20"
                        data-testid="iv-fullscreen"
                        title="Fullscreen (f)"
                    >
                        {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                    </Button>
                    <Button
                        size="icon"
                        variant="ghost"
                        onClick={onClose}
                        aria-label="Close image viewer"
                        className="text-white hover:bg-rose-500/30"
                        data-testid="iv-close"
                    >
                        <X className="w-5 h-5" />
                    </Button>
                </div>
            </div>

            {/* Image area */}
            <div
                className="absolute inset-0 flex items-center justify-center overflow-hidden"
                onMouseDown={onMouseDown}
                onMouseMove={onMouseMove}
                onMouseUp={onMouseUp}
                onMouseLeave={onMouseUp}
                onWheel={onWheel}
                style={{ cursor: dragging ? "grabbing" : zoom > 1 ? "grab" : "default" }}
            >
                {sideBySide ? (
                    <div className="w-full h-full overflow-x-auto overflow-y-hidden">
                        <div className="flex items-center gap-4 px-12 py-12 min-w-max h-full">
                            {images.map((img, i) => (
                                <figure
                                    key={img.id}
                                    className="relative flex-shrink-0 flex flex-col items-center"
                                    data-testid="iv-tile"
                                >
                                    {img.file_url ? (
                                        <img
                                            src={img.file_url}
                                            alt={img.caption || `Image ${i + 1}`}
                                            className="max-h-[70vh] object-contain rounded"
                                            style={{ transform: `rotate(${rotate}deg)` }}
                                        />
                                    ) : (
                                        <div className="w-64 h-40 flex items-center justify-center text-slate-400">
                                            <ImageIcon className="w-10 h-10" />
                                        </div>
                                    )}
                                    <figcaption className="mt-2 text-xs text-white/80 max-w-[20rem] text-center">
                                        {img.caption || `Image ${i + 1}`}
                                    </figcaption>
                                    {annotationsOn && img.modality && img.modality !== 'other' ? (
                                        <span className="absolute top-1 left-1 rounded bg-violet-600/80 px-1.5 py-0.5 text-[10px] text-white uppercase tracking-wide">
                                            {img.modality}
                                        </span>
                                    ) : null}
                                </figure>
                            ))}
                        </div>
                    </div>
                ) : current?.file_url ? (
                    <img
                        src={current.file_url}
                        alt={current.caption || 'Question image'}
                        className="max-w-none max-h-none select-none"
                        draggable={false}
                        style={{
                            transform: `translate(${pos.x}px, ${pos.y}px) scale(${zoom}) rotate(${rotate}deg)`,
                            transition: dragging ? "none" : "transform 120ms ease-out",
                            maxHeight: "85vh",
                            maxWidth: "90vw",
                        }}
                        data-testid="iv-image"
                    />
                ) : (
                    <div className="flex flex-col items-center text-slate-300">
                        <ImageIcon className="w-16 h-16 mb-3" />
                        <p>Image not available</p>
                    </div>
                )}
            </div>

            {/* Annotation overlay (single-image mode) */}
            {!sideBySide && annotationsOn && current ? (
                <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-1 pointer-events-none">
                    <span className="rounded-full bg-black/60 backdrop-blur px-3 py-1 text-xs text-white">
                        {current.caption || `Image ${index + 1}`}
                        {current.page_number ? ` · p.${current.page_number}` : ''}
                        {current.image_index_in_page != null ? ` · #${current.image_index_in_page + 1}` : ''}
                    </span>
                </div>
            ) : null}

            {/* Prev / Next (single-image mode) */}
            {!sideBySide && images.length > 1 ? (
                <>
                    <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => setIndex((i) => Math.max(0, i - 1))}
                        disabled={index === 0}
                        aria-label="Previous image"
                        className="absolute left-3 top-1/2 -translate-y-1/2 z-10 text-white hover:bg-white/20 disabled:opacity-30"
                    >
                        <ChevronLeft className="w-6 h-6" />
                    </Button>
                    <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => setIndex((i) => Math.min(images.length - 1, i + 1))}
                        disabled={index === images.length - 1}
                        aria-label="Next image"
                        className="absolute right-3 top-1/2 -translate-y-1/2 z-10 text-white hover:bg-white/20 disabled:opacity-30"
                    >
                        <ChevronRight className="w-6 h-6" />
                    </Button>
                </>
            ) : null}

            {/* Hint */}
            <div className="absolute bottom-3 right-3 z-10 text-[10px] text-white/60 select-none pointer-events-none">
                +/− zoom · 0 reset · f fullscreen · a annotations · s side-by-side · ←/→ navigate
            </div>
        </div>
    );
}
