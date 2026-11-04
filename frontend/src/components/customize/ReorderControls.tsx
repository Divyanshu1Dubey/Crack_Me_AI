'use client';

import { ChevronDown, ChevronUp } from 'lucide-react';

const ICON_BUTTON =
    'inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-background text-foreground ' +
    'transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ' +
    'disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-background';

/**
 * Up / down buttons of one row. `moveKey` names the row (`data-move="<key>:up|down"`), so the
 * Customise section can put the focus back on the row's button after it moved.
 */
export function MoveButtons({
    moveKey,
    label,
    isFirst,
    isLast,
    disabled = false,
    onMove,
}: {
    moveKey: string;
    /** What moves, for the buttons' names ("Move Question Bank up"). */
    label: string;
    isFirst: boolean;
    isLast: boolean;
    disabled?: boolean;
    onMove: (direction: -1 | 1) => void;
}) {
    return (
        <div className="flex shrink-0 items-center gap-1">
            <button
                type="button"
                data-move={`${moveKey}:up`}
                onClick={() => onMove(-1)}
                disabled={disabled || isFirst}
                aria-label={`Move ${label} up`}
                title="Move up"
                className={ICON_BUTTON}
            >
                <ChevronUp className="h-4 w-4" aria-hidden="true" />
            </button>
            <button
                type="button"
                data-move={`${moveKey}:down`}
                onClick={() => onMove(1)}
                disabled={disabled || isLast}
                aria-label={`Move ${label} down`}
                title="Move down"
                className={ICON_BUTTON}
            >
                <ChevronDown className="h-4 w-4" aria-hidden="true" />
            </button>
        </div>
    );
}

/** An on / off switch (a button with role="switch"; Space and Enter toggle it). */
export function VisibilitySwitch({
    checked,
    label,
    disabled = false,
    title,
    onChange,
}: {
    checked: boolean;
    /** The switch's name, e.g. "Show Quests in the sidebar". */
    label: string;
    disabled?: boolean;
    title?: string;
    onChange: (checked: boolean) => void;
}) {
    return (
        <button
            type="button"
            role="switch"
            aria-checked={checked}
            aria-label={label}
            title={title ?? label}
            disabled={disabled}
            onClick={() => onChange(!checked)}
            className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 ${checked ? 'bg-primary' : 'bg-muted-foreground/30'}`}
        >
            <span
                aria-hidden="true"
                className={`inline-block h-5 w-5 rounded-full bg-background shadow-sm transition-transform ${checked ? 'translate-x-5' : 'translate-x-0.5'}`}
            />
        </button>
    );
}
