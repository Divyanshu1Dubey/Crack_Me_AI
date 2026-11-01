import type { Metadata } from "next";
import { Manrope, Space_Grotesk } from "next/font/google";
import Script from "next/script";
import { Suspense } from "react";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ThemeSync } from "@/components/ThemeSync";
import BackendWarmup from "@/components/BackendWarmup";
import { TooltipProvider } from "@/components/ui/tooltip";
import DatadogInit from "@/components/DatadogInit";
import TrafficAnalytics from "@/components/TrafficAnalytics";
import ClarityInit from "@/components/ClarityInit";
import PostHogInit from "@/components/PostHogInit";
import ConsentBanner from "@/components/ConsentBanner";
import StickyExamCta from "@/components/StickyExamCta";
import PWAProvider from "@/components/PWAProvider";
import { ExamTrackProvider } from "@/components/ExamTrackProvider";
import { ProfileAutoRefreshMount } from "@/components/ProfileAutoRefreshMount";
import { DockProvider } from "@/context/DockContext";
import { SidebarProvider } from "@/context/SidebarContext";
import { QuestionFocusProvider } from "@/context/QuestionFocusContext";
import { FloatingDock } from "@/components/FloatingDock";
import { PaywallRoot } from "@/components/paywall/PaywallRoot";
import { PaywallProvider } from "@/lib/paywall/paywallContext";
import Footer from "@/components/Footer";
import { defaultOgImage, seoKeywords, siteDescription, siteName, siteTitle, siteUrl } from "@/lib/seo";
import { graphSchema, jsonLdString, orgSchema, websiteSchema } from "@/lib/metadata";

const gaMeasurementId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "G-MM88RT1QQK";
const analyticsInDev = process.env.NEXT_PUBLIC_ANALYTICS_IN_DEV === "true";
const shouldInjectGoogleTag =
  Boolean(gaMeasurementId) && (process.env.NODE_ENV === "production" || analyticsInDev);

// Preconnect to critical origins to shave RTT off LCP
const apiOrigin = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "").replace(/\/api$/, "");

// latin-ext ensures curly quotes ('), em-dashes (—), ellipsis (…), and common
// European diacritics render correctly. Without it, characters fall back to the
// system font, which produced tofu boxes ("ΓÇÿXΓÇÖ") in PYQ question text.
const manrope = Manrope({
  subsets: ["latin", "latin-ext"],
  variable: "--font-manrope",
  display: "swap",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin", "latin-ext"],
  variable: "--font-space-grotesk",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: siteTitle,
    template: `%s | ${siteName}`,
  },
  // Google Search Console verification — set NEXT_PUBLIC_GSC_VERIFICATION to
  // the HTML-tag token from https://search.google.com/search-console. No tag
  // is emitted when it is unset (a placeholder token used to be published).
  ...(process.env.NEXT_PUBLIC_GSC_VERIFICATION
    ? { verification: { google: process.env.NEXT_PUBLIC_GSC_VERIFICATION } }
    : {}),
  other: {
    'msvalidate.01': process.env.NEXT_PUBLIC_BING_VERIFICATION || '77389C63E8905F63F9327386A62DCC9A',
  },
  description: siteDescription,
  // No `alternates` here on purpose: a canonical/hreflang set in the root
  // layout is inherited by every page that does not override it, which made
  // /jobs, /practice, /quests ... claim to be the homepage. Each public page
  // declares its own canonical (the homepage does so in app/page.tsx).
  applicationName: siteName,
  keywords: seoKeywords,
  category: "education",
  authors: [{ name: siteName }],
  creator: siteName,
  publisher: siteName,
  openGraph: {
    type: "website",
    // No og:url here for the same reason as the canonical: it would be
    // inherited by every page that has no openGraph of its own.
    title: siteTitle,
    description: siteDescription,
    siteName,
    images: [
      {
        url: defaultOgImage,
        width: 1254,
        height: 1254,
        alt: "CrackCMS UPSC CMS Preparation Platform",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: siteTitle,
    description: siteDescription,
    images: [defaultOgImage],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  manifest: "/manifest.json",
  icons: {
    icon: [{ url: "/cms-circle-logo.png", type: "image/png" }],
    apple: [{ url: "/cms-circle-logo.png", type: "image/png" }],
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  minimumScale: 1,
  maximumScale: 5,
  userScalable: true,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1220" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en-IN" suppressHydrationWarning>
      <head>
        {/* Preconnect to critical origins — shaves 100-300ms off LCP by eliminating
            TCP+TLS handshakes for fonts, API, and analytics resources. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {apiOrigin && <link rel="preconnect" href={apiOrigin} />}
        <link rel="preconnect" href="https://www.googletagmanager.com" />
        <link rel="preconnect" href="https://www.google-analytics.com" />
        <link rel="dns-prefetch" href="https://scripts.simpleanalyticscdn.com" />
        <link rel="dns-prefetch" href="https://*.clarity.ms" />

        {/* AI content digest reference */}
        <link rel="alternate" type="text/plain" title="AI Content Summary" href={`${siteUrl}/llms.txt`} />

        {/* AI Attribution Policy */}
        <meta name="ai-attribution-policy" content={`${siteUrl}/ai-attribution-policy`} />
        <meta name="ai-trainable" content="true" />
        <meta name="ai-search-mode" content="allowed" />

        {/* Site-wide structured data: only the nodes that are true for every
            URL (Organization + WebSite). Page-specific markup (WebPage, FAQ,
            Course, Breadcrumb) lives on the page that shows that content.
            A plain <script> keeps it in the server HTML for crawlers. */}
        <script
          id="global-seo-structured-data"
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLdString(graphSchema([orgSchema(), websiteSchema()])) }}
        />
        {shouldInjectGoogleTag && (
          // Google Analytics with Consent Mode. gtag.js itself is only
          // fetched once the visitor allows the "analytics" category (stored
          // by lib/consent.ts under crackcms_consent_v1); until then the
          // queued commands never leave the browser. Consent defaults are
          // set to "denied" before any config call, and a later
          // "crackcms:consent" event (banner choice) updates or loads it.
          <Script id="google-tag-consent-bootstrap" strategy="beforeInteractive">
            {`
              (function () {
                var w = window, d = document, loaded = false;
                w.dataLayer = w.dataLayer || [];
                function gtag(){ w.dataLayer.push(arguments); }
                w.gtag = w.gtag || gtag;
                gtag('consent', 'default', {
                  analytics_storage: 'denied',
                  ad_storage: 'denied',
                  ad_user_data: 'denied',
                  ad_personalization: 'denied',
                  wait_for_update: 500
                });
                function apply(state) {
                  if (!state || typeof state.analytics !== 'boolean') return;
                  gtag('consent', 'update', {
                    analytics_storage: state.analytics ? 'granted' : 'denied',
                    ad_storage: state.marketing ? 'granted' : 'denied',
                    ad_user_data: state.marketing ? 'granted' : 'denied',
                    ad_personalization: state.marketing ? 'granted' : 'denied'
                  });
                  if (state.analytics && !loaded) {
                    loaded = true;
                    var s = d.createElement('script');
                    s.async = true;
                    s.src = 'https://www.googletagmanager.com/gtag/js?id=${gaMeasurementId}';
                    (d.head || d.documentElement).appendChild(s);
                  }
                }
                try { apply(JSON.parse(w.localStorage.getItem('crackcms_consent_v1') || 'null')); } catch (e) {}
                gtag('js', new Date());
                gtag('config', '${gaMeasurementId}', { send_page_view: false });
                w.addEventListener('crackcms:consent', function (e) { apply(e && e.detail); });
              })();
            `}
          </Script>
        )}
      </head>
      <body className={`${manrope.variable} ${spaceGrotesk.variable} font-sans antialiased`}>
        <a href="#main-content" className="skip-link">Skip to main content</a>
        <PWAProvider>
          <ThemeProvider attribute="data-theme" defaultTheme="system" enableSystem storageKey="crackcms-theme">
            <ThemeSync />
            <TooltipProvider>
              <PaywallProvider>
                <AuthProvider>
                  <ProfileAutoRefreshMount />
                  <ExamTrackProvider>
                    <SidebarProvider>
                      <QuestionFocusProvider>
                        <DockProvider>
                          <DatadogInit />
                          <ClarityInit />
                          <PostHogInit />
                          <Suspense fallback={null}>
                            <TrafficAnalytics />
                          </Suspense>
                          <BackendWarmup />
                          <main id="main-content">{children}</main>
                          <Footer />
                          <FloatingDock />
                          <StickyExamCta />
                          <ConsentBanner />
                          <PaywallRoot />
                        </DockProvider>
                      </QuestionFocusProvider>
                    </SidebarProvider>
                  </ExamTrackProvider>
                </AuthProvider>
              </PaywallProvider>
            </TooltipProvider>
          </ThemeProvider>
        </PWAProvider>
      </body>
    </html>
  );
}
