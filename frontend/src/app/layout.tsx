import type { Metadata } from "next";
import { Manrope, Space_Grotesk } from "next/font/google";
import Script from "next/script";
import { Suspense } from "react";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/components/ThemeProvider";
import BackendWarmup from "@/components/BackendWarmup";
import { TooltipProvider } from "@/components/ui/tooltip";
import DatadogInit from "@/components/DatadogInit";
import TrafficAnalytics from "@/components/TrafficAnalytics";
import StickyExamCta from "@/components/StickyExamCta";
import { seoKeywords, siteDescription, siteName, siteTitle, siteUrl } from "@/lib/seo";

const gaMeasurementId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "G-SW77S58LX0";
const analyticsInDev = process.env.NEXT_PUBLIC_ANALYTICS_IN_DEV === "true";
const shouldInjectGoogleTag =
  Boolean(gaMeasurementId) && (process.env.NODE_ENV === "production" || analyticsInDev);

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-manrope",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
});

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: siteTitle,
    template: `%s | ${siteName}`,
  },
  description: siteDescription,
  applicationName: siteName,
  keywords: seoKeywords,
  category: "education",
  authors: [{ name: siteName }],
  creator: siteName,
  publisher: siteName,
  openGraph: {
    type: "website",
    url: siteUrl,
    title: siteTitle,
    description: siteDescription,
    siteName,
    images: [
      {
        url: "/crack-cms-logo.jpg",
        width: 1200,
        height: 630,
        alt: "CrackCMS UPSC CMS Preparation Platform",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: siteTitle,
    description: siteDescription,
    images: ["/crack-cms-logo.jpg"],
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
  manifest: "/site.webmanifest",
  icons: {
    icon: [{ url: "/crack-cms-logo.jpg", type: "image/jpeg" }],
    apple: [{ url: "/crack-cms-logo.jpg", type: "image/jpeg" }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <Script id="global-seo-structured-data" type="application/ld+json" strategy="beforeInteractive">
          {JSON.stringify({
            "@context": "https://schema.org",
            "@graph": [
              {
                "@type": "Organization",
                name: siteName,
                url: siteUrl,
                logo: `${siteUrl}/crack-cms-logo.jpg`,
                description: siteDescription,
              },
              {
                "@type": "EducationalOrganization",
                name: `${siteName} Medical Exam Prep`,
                url: siteUrl,
                description: "UPSC CMS and NEET PG focused online preparation platform for medical graduates.",
              },
              {
                "@type": "WebSite",
                name: siteName,
                url: siteUrl,
                inLanguage: "en-IN",
                potentialAction: {
                  "@type": "SearchAction",
                  target: `${siteUrl}/questions?search={search_term_string}`,
                  "query-input": "required name=search_term_string",
                },
              },
            ],
          })}
        </Script>
        {shouldInjectGoogleTag && (
          <>
            <Script
              id="google-tag-src"
              src={`https://www.googletagmanager.com/gtag/js?id=${gaMeasurementId}`}
              strategy="beforeInteractive"
            />
            <Script id="google-tag-inline" strategy="beforeInteractive">
              {`
                window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                window.gtag = window.gtag || gtag;
                gtag('js', new Date());
                gtag('config', '${gaMeasurementId}', { send_page_view: false });
              `}
            </Script>
          </>
        )}
      </head>
      <body className={`${manrope.variable} ${spaceGrotesk.variable} font-sans antialiased`}>
        <a href="#main-content" className="skip-link">Skip to main content</a>
        <ThemeProvider attribute="data-theme" defaultTheme="light" enableSystem>
          <TooltipProvider>
            <AuthProvider>
              <DatadogInit />
              <Suspense fallback={null}>
                <TrafficAnalytics />
              </Suspense>
              <BackendWarmup />
              <main id="main-content">{children}</main>
              <StickyExamCta />
            </AuthProvider>
          </TooltipProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
