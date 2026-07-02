import type { Metadata } from 'next';
import type { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'Contact Us | CrackLabs',
  description: 'Get in touch with CrackLabs support and UPSC CMS team.',
};

export default function ContactLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
