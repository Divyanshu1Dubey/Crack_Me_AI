'use client';

import { useEffect, useMemo, useRef } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';
import Script from 'next/script';

declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
    sa_pageview?: () => void;
  }
}

const GA_MEASUREMENT_ID = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || 'G-SW77S58LX0';
const SIMPLE_ANALYTICS_ENABLED = (process.env.NEXT_PUBLIC_SIMPLE_ANALYTICS_ENABLED ?? 'true') !== 'false';
const ANALYTICS_IN_DEV = (process.env.NEXT_PUBLIC_ANALYTICS_IN_DEV ?? 'false') === 'true';

export default function TrafficAnalytics() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const isEnabled = process.env.NODE_ENV === 'production' || ANALYTICS_IN_DEV;
  const shouldLoadGA = isEnabled && Boolean(GA_MEASUREMENT_ID);
  const shouldLoadSimpleAnalytics = isEnabled && SIMPLE_ANALYTICS_ENABLED;
  const lastSimpleAnalyticsPath = useRef<string | null>(null);

  const currentPath = useMemo(() => {
    if (!pathname) return '/';
    const query = searchParams?.toString();
    return query ? `${pathname}?${query}` : pathname;
  }, [pathname, searchParams]);

  useEffect(() => {
    if (!shouldLoadGA || typeof window === 'undefined') return;

    window.dataLayer = window.dataLayer || [];
    if (typeof window.gtag !== 'function') {
      window.gtag = (...args: unknown[]) => {
        window.dataLayer?.push(args);
      };
    }

    window.gtag('event', 'page_view', {
      page_path: currentPath,
      page_location: `${window.location.origin}${currentPath}`,
      page_title: document.title,
    });
  }, [currentPath, shouldLoadGA]);

  useEffect(() => {
    if (!shouldLoadSimpleAnalytics || typeof window === 'undefined') return;

    if (lastSimpleAnalyticsPath.current === null) {
      lastSimpleAnalyticsPath.current = currentPath;
      return;
    }

    if (lastSimpleAnalyticsPath.current !== currentPath && typeof window.sa_pageview === 'function') {
      window.sa_pageview();
      lastSimpleAnalyticsPath.current = currentPath;
    }
  }, [currentPath, shouldLoadSimpleAnalytics]);

  if (!shouldLoadGA && !shouldLoadSimpleAnalytics) return null;

  return (
    <>
      {shouldLoadSimpleAnalytics && (
        <Script
          id="simple-analytics"
          data-collect-dnt="true"
          src="https://scripts.simpleanalyticscdn.com/latest.js"
          strategy="afterInteractive"
        />
      )}

      {shouldLoadGA && (
        <>
          <Script
            id="ga4-src"
            src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`}
            strategy="afterInteractive"
          />
          <Script id="ga4-inline" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              window.gtag = gtag;
              gtag('js', new Date());
              gtag('config', '${GA_MEASUREMENT_ID}', { send_page_view: false });
            `}
          </Script>
        </>
      )}
    </>
  );
}