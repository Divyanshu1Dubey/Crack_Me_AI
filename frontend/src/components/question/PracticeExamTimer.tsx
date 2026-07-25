"use client";
/**
 * PracticeExamTimer — whole-session countdown for `timed` practice mode.
 *
 * Counts down from `totalSeconds`. When it hits zero, callers'
 * onExpire fires once. Pauses automatically when the tab is hidden;
 * resumes on visibility. Renders a small pill in the player header.
 */
import { useEffect, useRef, useState } from "react";
import { Clock } from "lucide-react";

interface Props {
    totalSeconds: number;
    onExpire?: () => void;
}

function fmt(seconds: number): string {
    if (seconds < 0) seconds = 0;
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    return `${m}:${String(s).padStart(2, "0")}`;
}

export default function PracticeExamTimer({ totalSeconds, onExpire }: Props) {
    const [remaining, setRemaining] = useState(totalSeconds);
    const expiresAtRef = useRef<number | null>(null);
    const expiredRef = useRef(false);

    // Start / restart the timer when totalSeconds changes.
    useEffect(() => {
        expiresAtRef.current = Date.now() + totalSeconds * 1000;
        expiredRef.current = false;
        setRemaining(totalSeconds);
    }, [totalSeconds]);

    // Tick.
    useEffect(() => {
        const tick = () => {
            if (expiresAtRef.current == null) return;
            const left = Math.max(0, Math.round((expiresAtRef.current - Date.now()) / 1000));
            setRemaining(left);
            if (left === 0 && !expiredRef.current) {
                expiredRef.current = true;
                onExpire?.();
            }
        };
        tick();
        const interval = setInterval(tick, 1000);
        return () => clearInterval(interval);
    }, [onExpire]);

    // Auto-pause when tab hidden.
    useEffect(() => {
        let hiddenAt: number | null = null;
        const onVis = () => {
            if (document.hidden) {
                hiddenAt = Date.now();
            } else if (hiddenAt != null && expiresAtRef.current != null) {
                // Add the hidden duration back to the deadline so the timer
                // effectively pauses while the tab is hidden.
                expiresAtRef.current += Date.now() - hiddenAt;
                hiddenAt = null;
            }
        };
        document.addEventListener("visibilitychange", onVis);
        return () => document.removeEventListener("visibilitychange", onVis);
    }, []);

    const warn = remaining <= 60;
    const danger = remaining <= 10;

    return (
        <div
            className={`mb-3 inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-semibold
                        ${danger ? "bg-rose-900/60 text-rose-100" :
                          warn ? "bg-amber-900/60 text-amber-100" :
                          "bg-slate-800/80 text-slate-100"}`}
            role="status"
            aria-live="polite"
        >
            <Clock className="h-4 w-4" />
            <span>{fmt(remaining)}</span>
        </div>
    );
}
