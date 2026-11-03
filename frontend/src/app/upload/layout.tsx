import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Upload',
  robots: { index: false, follow: false },
  alternates: { canonical: '/upload' },
};

// No AppShell here: the page renders the app shell itself (Sidebar + Header,
// the inline pattern of most app pages), and a page inside an AppShell layout
// must render neither (contract C6). Wrapping it here would show two shells.
export default function UploadLayout({ children }: { children: ReactNode }) {
  return children;
}
