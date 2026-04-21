import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Upload',
  robots: { index: false, follow: false },
  alternates: { canonical: '/upload' },
};

export default function UploadLayout({ children }: { children: ReactNode }) {
  return children;
}
