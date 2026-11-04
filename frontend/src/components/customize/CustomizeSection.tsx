'use client';

/**
 * Settings > Customise: the order of the sidebar's sections and links, which links show (the others
 * move to the sidebar's "More" group), the order and visibility of the dashboard widgets, and the
 * page the app opens on. Every change applies at once and is saved to the account
 * (preferencesStore.ts); "Reset to default" restores everything. Controls stay disabled until the
 * server's copy is loaded, so an edit never builds on an older layout.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { RotateCcw, SlidersHorizontal } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { useExamTrack } from '@/components/ExamTrackProvider';
import {
    DASHBOARD_WIDGETS,
    LANDING_PAGE_IDS,
    compactDashboard,
    compactSidebar,
    dashboardHidden,
    dashboardOrder,
    isLandingPageId,
    landingPageLabel,
    landingPageOf,
    moveId,
    navItemAvailable,
    sectionItemOrder,
    sidebarHidden,
    sidebarItem,
    sidebarItemOrder,
    sidebarSectionOrder,
    widgetAlwaysShown,
    SIDEBAR_SECTIONS,
    type DashboardWidgetId,
    type NavItemDef,
} from '@/lib/preferences';
import { MoveButtons, VisibilitySwitch } from './ReorderControls';
import { refreshPreferences, resetPreferences, updatePreferences } from './preferencesStore';
import { useUiPreferences } from './usePreferences';

const SECTION_BY_ID = new Map(SIDEBAR_SECTIONS.map((section) => [section.id, section]));

interface SectionRows {
    id: string;
    title: string;
    items: NavItemDef[];
}

export default function CustomizeSection() {
    const { user } = useAuth();
    const { activeTrack, hydrated } = useExamTrack();
    const { prefs, loaded, saving, saveError, signedIn } = useUiPreferences();
    const rootRef = useRef<HTMLElement | null>(null);
    const focusAfterMove = useRef<{ key: string; direction: -1 | 1 } | null>(null);
    const wasSaving = useRef(false);
    const [announcement, setAnnouncement] = useState('');
    const [justSaved, setJustSaved] = useState(false);

    const isAdmin = user?.role === 'admin' || user?.is_admin === true;
    const isPremium = isAdmin || user?.is_premium === true || user?.subscription_info?.is_active === true;
    const viewer = { isAdmin, track: hydrated ? activeTrack : 'cms' };
    const canEdit = signedIn && loaded;

    // Ask the server again when Settings opens in a session that already loaded the layout.
    useEffect(() => {
        if (loaded) refreshPreferences();
    }, []);

    // After a move, keep the focus on the row's button (or the other one, at the top / bottom).
    useEffect(() => {
        const target = focusAfterMove.current;
        if (!target) return;
        focusAfterMove.current = null;
        const root = rootRef.current;
        if (!root) return;
        const find = (direction: -1 | 1) => root.querySelector<HTMLButtonElement>(
            `[data-move="${target.key}:${direction === -1 ? 'up' : 'down'}"]`,
        );
        const same = find(target.direction);
        (same && !same.disabled ? same : find(target.direction === -1 ? 1 : -1))?.focus();
    });

    // "Saved" for a moment after a save went through.
    useEffect(() => {
        const finished = wasSaving.current && !saving && !saveError;
        wasSaving.current = saving;
        if (!finished) return;
        setJustSaved(true);
        const timeout = window.setTimeout(() => setJustSaved(false), 2500);
        return () => window.clearTimeout(timeout);
    }, [saving, saveError]);

    const sectionOrder = sidebarSectionOrder(prefs.sidebar);
    const itemOrder = sidebarItemOrder(prefs.sidebar);
    const hiddenItems = sidebarHidden(prefs.sidebar);
    const widgetOrder = dashboardOrder(prefs.dashboard);
    const hiddenWidgets = dashboardHidden(prefs.dashboard);
    const landing = landingPageOf(prefs);
    const customised = Object.keys(prefs).length > 0;

    // What this learner sees: admin-only and exam-track links, the upgrade row of the free plan.
    const sections: SectionRows[] = [];
    for (const sectionId of sectionOrder) {
        const section = SECTION_BY_ID.get(sectionId);
        if (!section) continue;
        const items = sectionItemOrder(sectionId, prefs.sidebar)
            .map((id) => sidebarItem(id))
            .filter((item): item is NavItemDef => item !== undefined && navItemAvailable(item, viewer));
        if (items.length) sections.push({ id: section.id, title: section.title, items });
    }
    const widgets = widgetOrder.filter((id) => !(isPremium && id === 'upgrade'));

    const position = (ids: readonly string[], id: string, scope: string) =>
        `${ids.indexOf(id) + 1} of ${ids.length}${scope}`;

    const saveSidebar = (sectionIds: readonly string[], itemIds: readonly string[], hidden: Iterable<string>) => {
        updatePreferences({ sidebar: compactSidebar(sectionIds, itemIds, hidden) });
    };

    const moveSection = (sectionId: string, direction: -1 | 1) => {
        const visibleIds = sections.map((section) => section.id);
        const next = moveId(sectionOrder, sectionId, direction, visibleIds);
        focusAfterMove.current = { key: `section-${sectionId}`, direction };
        saveSidebar(next, itemOrder, hiddenItems);
        const title = SECTION_BY_ID.get(sectionId)?.title ?? sectionId;
        setAnnouncement(`${title} section moved ${direction === -1 ? 'up' : 'down'}: ${position(next.filter((id) => visibleIds.includes(id)), sectionId, '')}.`);
    };

    const moveItem = (sectionId: string, item: NavItemDef, direction: -1 | 1) => {
        const among = sections.find((section) => section.id === sectionId)?.items.map((own) => own.id) ?? [];
        const next = moveId(itemOrder, item.id, direction, among);
        focusAfterMove.current = { key: `item-${item.id}`, direction };
        saveSidebar(sectionOrder, next, hiddenItems);
        const title = SECTION_BY_ID.get(sectionId)?.title ?? '';
        setAnnouncement(`${item.label} moved ${direction === -1 ? 'up' : 'down'}: ${position(next.filter((id) => among.includes(id)), item.id, ` in ${title}`)}.`);
    };

    const toggleItem = (item: NavItemDef, show: boolean) => {
        const hidden = new Set(hiddenItems);
        if (show) hidden.delete(item.id);
        else hidden.add(item.id);
        saveSidebar(sectionOrder, itemOrder, hidden);
        setAnnouncement(show ? `${item.label} is back in the sidebar.` : `${item.label} moved under More in the sidebar.`);
    };

    const moveWidget = (id: DashboardWidgetId, direction: -1 | 1) => {
        const next = moveId(widgetOrder, id, direction, widgets);
        focusAfterMove.current = { key: `widget-${id}`, direction };
        updatePreferences({ dashboard: compactDashboard(next, hiddenWidgets) });
        setAnnouncement(`${DASHBOARD_WIDGETS[id].label} moved ${direction === -1 ? 'up' : 'down'}: ${position(next.filter((w) => widgets.includes(w)), id, ' on the dashboard')}.`);
    };

    const toggleWidget = (id: DashboardWidgetId, show: boolean) => {
        const hidden = new Set(hiddenWidgets);
        if (show) hidden.delete(id);
        else hidden.add(id);
        updatePreferences({ dashboard: compactDashboard(widgetOrder, hidden) });
        setAnnouncement(`${DASHBOARD_WIDGETS[id].label} ${show ? 'shown on' : 'hidden from'} the dashboard.`);
    };

    const changeLanding = (value: string) => {
        if (!isLandingPageId(value)) return;
        // The default is not stored.
        updatePreferences({ landing_page: value === 'dashboard' ? null : value }, { immediate: true });
        setAnnouncement(`The app now opens on ${landingPageLabel(value)}.`);
    };

    const handleReset = () => {
        if (!window.confirm('Reset the sidebar, the dashboard and the opening page to the default layout?')) return;
        resetPreferences();
        setAnnouncement('The default layout is back.');
    };

    let status: ReactNode = 'Changes are saved to your account and apply on every device you sign in on.';
    if (!loaded && signedIn) status = 'Loading your layout…';
    else if (saving) status = 'Saving…';
    else if (justSaved) status = 'Saved.';

    return (
        <section
            id="customise"
            ref={rootRef}
            aria-labelledby="customise-heading"
            className="glass-card p-4 sm:p-6 scroll-mt-24"
        >
            <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                <h3 id="customise-heading" className="font-bold flex items-center gap-2 text-foreground">
                    <SlidersHorizontal className="w-5 h-5 text-primary" aria-hidden="true" />
                    Customise
                </h3>
                <button
                    type="button"
                    onClick={handleReset}
                    disabled={!canEdit || !customised}
                    className="btn-secondary text-xs inline-flex items-center gap-1.5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    <RotateCcw className="w-3.5 h-3.5" aria-hidden="true" />
                    Reset to default
                </button>
            </div>
            <p className="text-xs text-muted-foreground mb-5">
                Put what you use most at the top and hide what you don&apos;t. Nothing is removed: hidden
                sidebar links stay under <strong className="font-semibold text-foreground">More</strong>, and hidden
                dashboard sections can be switched back on here.
            </p>

            {/* Opening page */}
            <div className="mb-6 space-y-1.5">
                <label htmlFor="customise-landing" className="block text-sm font-medium text-foreground">
                    Open the app on
                </label>
                <select
                    id="customise-landing"
                    className="input-field"
                    value={landing}
                    disabled={!canEdit}
                    onChange={(event) => changeLanding(event.target.value)}
                    aria-describedby="customise-landing-hint"
                >
                    {LANDING_PAGE_IDS.map((id) => (
                        <option key={id} value={id}>{landingPageLabel(id)}</option>
                    ))}
                </select>
                <p id="customise-landing-hint" className="text-xs text-muted-foreground">
                    Where you land after signing in or opening CrackLabs. The Dashboard link always opens the dashboard.
                </p>
            </div>

            {/* Sidebar */}
            <div role="group" aria-labelledby="customise-sidebar-heading" className="mb-6">
                <h4 id="customise-sidebar-heading" className="text-sm font-semibold text-foreground">Sidebar</h4>
                <p className="text-xs text-muted-foreground mt-0.5 mb-3">
                    Move sections and links up or down. Switch a link off to move it under More.
                </p>
                <ol className="space-y-3">
                    {sections.map((section, sectionIndex) => (
                        <li key={section.id} className="rounded-xl border border-border bg-card">
                            <div className="flex items-center gap-2 border-b border-border px-3 py-2">
                                <span className="min-w-0 flex-1 truncate text-xs font-bold uppercase tracking-wider text-muted-foreground">
                                    {section.title}
                                </span>
                                <MoveButtons
                                    moveKey={`section-${section.id}`}
                                    label={`the ${section.title} section`}
                                    isFirst={sectionIndex === 0}
                                    isLast={sectionIndex === sections.length - 1}
                                    disabled={!canEdit}
                                    onMove={(direction) => moveSection(section.id, direction)}
                                />
                            </div>
                            <ul className="divide-y divide-border">
                                {section.items.map((item, itemIndex) => {
                                    const shown = !hiddenItems.has(item.id);
                                    return (
                                        <li key={item.id} className="flex items-center gap-2 px-3 py-2">
                                            <span className={`min-w-0 flex-1 text-sm ${shown ? 'text-foreground' : 'text-muted-foreground'}`}>
                                                <span className="break-words">{item.label}</span>
                                                {!shown && (
                                                    <span className="ml-2 inline-block rounded-full bg-muted px-1.5 py-0.5 align-middle text-[10px] font-semibold text-muted-foreground">
                                                        Under More
                                                    </span>
                                                )}
                                            </span>
                                            <MoveButtons
                                                moveKey={`item-${item.id}`}
                                                label={item.label}
                                                isFirst={itemIndex === 0}
                                                isLast={itemIndex === section.items.length - 1}
                                                disabled={!canEdit}
                                                onMove={(direction) => moveItem(section.id, item, direction)}
                                            />
                                            <VisibilitySwitch
                                                checked={shown}
                                                label={`Show ${item.label} in the sidebar`}
                                                disabled={!canEdit}
                                                onChange={(show) => toggleItem(item, show)}
                                            />
                                        </li>
                                    );
                                })}
                            </ul>
                        </li>
                    ))}
                </ol>
            </div>

            {/* Dashboard */}
            <div role="group" aria-labelledby="customise-dashboard-heading">
                <h4 id="customise-dashboard-heading" className="text-sm font-semibold text-foreground">Dashboard</h4>
                <p className="text-xs text-muted-foreground mt-0.5 mb-3">
                    Move sections up or down, or switch off the ones you don&apos;t use.
                </p>
                <ol className="divide-y divide-border rounded-xl border border-border bg-card">
                    {widgets.map((id, index) => {
                        const widget = DASHBOARD_WIDGETS[id];
                        const fixed = widgetAlwaysShown(id);
                        const shown = fixed || !hiddenWidgets.has(id);
                        return (
                            <li key={id} className="flex items-center gap-2 px-3 py-2">
                                <span className="min-w-0 flex-1">
                                    <span className={`block text-sm break-words ${shown ? 'text-foreground' : 'text-muted-foreground'}`}>
                                        {widget.label}
                                    </span>
                                    <span className="block text-xs text-muted-foreground break-words">{widget.description}</span>
                                </span>
                                <MoveButtons
                                    moveKey={`widget-${id}`}
                                    label={widget.label}
                                    isFirst={index === 0}
                                    isLast={index === widgets.length - 1}
                                    disabled={!canEdit}
                                    onMove={(direction) => moveWidget(id, direction)}
                                />
                                <VisibilitySwitch
                                    checked={shown}
                                    label={`Show ${widget.label} on the dashboard`}
                                    title={fixed ? 'Always shown on the free plan' : undefined}
                                    disabled={!canEdit || fixed}
                                    onChange={(show) => toggleWidget(id, show)}
                                />
                            </li>
                        );
                    })}
                </ol>
            </div>

            {saveError ? (
                <p role="alert" className="mt-4 text-xs font-medium text-destructive">{saveError}</p>
            ) : (
                <p className="mt-4 text-xs text-muted-foreground">{status}</p>
            )}
            <p className="sr-only" aria-live="polite">{announcement}</p>
        </section>
    );
}
