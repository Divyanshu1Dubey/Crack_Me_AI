/**
 * SidebarAutoHide — route-level controller that auto-collapses the sidebar
 * on Question Bank routes.
 *
 * Behaviour:
 *   - When the user lands on any path starting with `/questions`, the
 *     sidebar collapses (unless the user has manually toggled it in the
 *     current session — the `userOverride` flag wins).
 *   - When they navigate away from `/questions*`, the override resets so
 *     the next visit to a questions route re-applies auto-collapse.
 *   - Renders nothing — pure side-effect component.
 *
 * Lives inside the questions layout tree (app/questions/layout.tsx) and
 * is also mounted by the dedicated practice routes that render their own
 * Sidebar (NEET PG / INI-CET).
 */
'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { useSidebar } from '@/context/SidebarContext';

const AUTO_COLLAPSE_PREFIX = '/questions';

export default function SidebarAutoHide() {
  const pathname = usePathname();
  const { collapseForRoute, resetOverride } = useSidebar();

  useEffect(() => {
    if (!pathname) return;
    const shouldAutoCollapse = pathname.startsWith(AUTO_COLLAPSE_PREFIX);

    if (shouldAutoCollapse) {
      collapseForRoute();
    } else {
      // Leaving the auto-collapse scope clears the session override so the
      // user doesn't have to navigate to a different scope to re-engage.
      resetOverride();
    }
  }, [pathname, collapseForRoute, resetOverride]);

  return null;
}