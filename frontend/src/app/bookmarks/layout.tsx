import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Bookmarks',
  robots: { index: false, follow: false },
  alternates: { canonical: '/bookmarks' },
};

export default function BookmarksLayout({ children }: { children: ReactNode }) {
  return children;
}
