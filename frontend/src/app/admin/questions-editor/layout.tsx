import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import AppShell from '@/components/AppShell';

export const metadata: Metadata = {
  title: 'Questions Editor',
  robots: { index: false, follow: false },
  alternates: { canonical: '/admin/questions-editor' },
};

// The page renders no Sidebar/Header of its own; the shell gives the admin
// tool the app navigation. Its `fixed inset-0` modals still cover the
// viewport because .main-content no longer uses layout containment.
export default function AdminQuestionsEditorLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
