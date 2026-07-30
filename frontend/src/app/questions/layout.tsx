import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import SidebarAutoHide from '@/components/SidebarAutoHide';

export const metadata: Metadata = {
  title: 'Questions',
  robots: { index: false, follow: false },
  alternates: { canonical: '/questions' },
};

export default function QuestionsLayout({ children }: { children: ReactNode }) {
  return (
    <>
      {/* Auto-collapse the desktop sidebar whenever the user is on any
          /questions* route. Manual user toggle still wins — see
          SidebarAutoHide + SidebarContext. */}
      <SidebarAutoHide />
      {children}
    </>
  );
}
