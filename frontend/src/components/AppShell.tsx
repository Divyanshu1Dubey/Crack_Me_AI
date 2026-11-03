import type { ReactNode } from 'react';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';

/**
 * AppShell — the signed-in app chrome (Sidebar + Header) around a page.
 *
 * Exactly the markup most app pages render inline. Route `layout.tsx`
 * files use it for pages that rendered without any navigation (Study
 * Time, Quests, Mistake Notebook, admin tools, ...); a page wrapped by
 * such a layout must not render its own Sidebar or Header.
 *
 * `.main-content` no longer uses layout containment (see globals.css), so
 * a page's own `fixed inset-0` overlays still cover the viewport inside it.
 */
export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div className="main-content">
        <Header />
        <div className="page-container">{children}</div>
      </div>
    </div>
  );
}
