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
import PWAProvider from "@/components/PWAProvider";
import { ExamTrackProvider } from "@/components/ExamTrackProvider";
import { WatermarkOverlay } from "@/components/WatermarkOverlay";
import { DockProvider } from "@/context/DockContext";
import { FloatingDock } from "@/components/FloatingDock";
import Footer from "@/components/Footer";
import { brandName, defaultOgImage, seoKeywords, siteDescription, siteName, siteTitle, siteUrl } from "@/lib/seo";
import { graphSchema, orgSchema, softwareAppSchema, websiteSchema } from "@/lib/metadata";

const gaMeasurementId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "G-MM88RT1QQK";
const analyticsInDev = process.env.NEXT_PUBLIC_ANALYTICS_IN_DEV === "true";
const shouldInjectGoogleTag =
  Boolean(gaMeasurementId) && (process.env.NODE_ENV === "production" || analyticsInDev);

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
  // Google Search Console verification — paste the meta-tag code from
  // https://search.google.com/search-console → URL Prefix → www.cracklabs.app
  // → Verification → HTML tag. Rendered as <meta name="google-site-verification">
  // by Next.js. Drop the value below; the env-var override is for Vercel.
  verification: {
    google: process.env.NEXT_PUBLIC_GSC_VERIFICATION || 'REPLACE_WITH_GSC_VERIFICATION_TOKEN',
  },
  other: {
    'msvalidate.01': process.env.NEXT_PUBLIC_BING_VERIFICATION || '77389C63E8905F63F9327386A62DCC9A',
  },
  description: siteDescription,
  alternates: {
    canonical: "/",
    languages: {
      "en-IN": "/",
      "en-US": "/",
      "en-GB": "/",
      "x-default": "/",
    },
  },
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
        url: defaultOgImage,
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
        <Script id="global-seo-structured-data" type="application/ld+json" strategy="beforeInteractive">
          {JSON.stringify(
            graphSchema([
              orgSchema(),
              websiteSchema(),
              {
                "@type": "WebPage",
                "@id": `${siteUrl}/#webpage`,
                url: siteUrl,
                name: siteTitle,
                description: siteDescription,
                isPartOf: { "@id": `${siteUrl}/#website` },
                about: { "@id": `${siteUrl}/#organization` },
                inLanguage: "en-IN",
              },
              softwareAppSchema(),
              {
                "@type": "Course",
                name: "UPSC CMS Complete Preparation Course",
                description:
                  "Comprehensive UPSC Combined Medical Services exam preparation with PYQs, AI-powered explanations, subject-wise mock tests and performance analytics.",
                provider: { "@id": `${siteUrl}/#organization` },
                url: `${siteUrl}/cms`,
                educationalLevel: "Postgraduate",
                inLanguage: "en-IN",
                hasCourseInstance: {
                  "@type": "CourseInstance",
                  courseMode: "online",
                  courseSchedule: { "@type": "Schedule", repeatFrequency: "P1D" },
                },
                offers: {
                  "@type": "Offer",
                  price: "199",
                  priceCurrency: "INR",
                  availability: "https://schema.org/InStock",
                },
              },
              {
                "@type": "Course",
                name: "NEET PG Complete Preparation Course",
                description:
                  "Medical PG revision with previous year questions, AI tutor, clinical MCQs and mock test simulator.",
                provider: { "@id": `${siteUrl}/#organization` },
                url: `${siteUrl}/neet-pg`,
                educationalLevel: "Postgraduate",
                inLanguage: "en-IN",
                offers: {
                  "@type": "Offer",
                  price: "199",
                  priceCurrency: "INR",
                  availability: "https://schema.org/InStock",
                },
              },
              {
                "@type": "FAQPage",
                mainEntity: [
                  {
                    "@type": "Question",
                    name: "What is CrackCMS?",
                    acceptedAnswer: {
                      "@type": "Answer",
                      text: "CrackCMS is an AI-powered preparation platform for UPSC CMS and medical entrance exams. It offers previous year questions, AI explanations, topic-wise practice, mock tests, flashcards and performance analytics.",
                    },
                  },
                  {
                    "@type": "Question",
                    name: "Is CrackCMS free for UPSC CMS preparation?",
                    acceptedAnswer: {
                      "@type": "Answer",
                      text: "Yes. CrackCMS offers a free tier for question practice and revision. Premium plans unlock broader AI tutor access, mock tests, analytics and study tools.",
                    },
                  },
                  {
                    "@type": "Question",
                    name: "How many previous year questions does CrackCMS have?",
                    acceptedAnswer: {
                      "@type": "Answer",
                      text: "CrackCMS organizes medical exam questions by subject, topic, year and difficulty. Questions include AI-generated explanations, references and clinical pearls where available.",
                    },
                  },
                  {
                    "@type": "Question",
                    name: "Does CrackCMS have NEET PG questions?",
                    acceptedAnswer: {
                      "@type": "Answer",
                      text: "Yes, CrackCMS includes a comprehensive NEET PG question bank with previous year papers from 2020-2025, AI-powered solutions, and subject-wise practice across General Medicine, Surgery, Pediatrics, OBG, and PSM.",
                    },
                  },
                  {
                    "@type": "Question",
                    name: "What AI features does CrackCMS offer?",
                    acceptedAnswer: {
                      "@type": "Answer",
                      text: "CrackCMS offers an AI Study Assistant trained on standard medical textbooks (Harrison's, Robbins, etc.), AI-powered question explanations with mnemonics and clinical pearls, an AI Question Generator for custom practice, and intelligent analytics that identify your weak areas.",
                    },
                  },
                ],
              },
              {
                "@type": "BreadcrumbList",
                itemListElement: [
                  { "@type": "ListItem", position: 1, name: "Home", item: siteUrl },
                  { "@type": "ListItem", position: 2, name: "UPSC CMS Preparation", item: `${siteUrl}/cms` },
                  { "@type": "ListItem", position: 3, name: "NEET PG Preparation", item: `${siteUrl}/neet-pg` },
                  { "@type": "ListItem", position: 4, name: "Pricing", item: `${siteUrl}/subscription` },
                ],
              },
            ])
          )}
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
        <PWAProvider>
          <ThemeProvider attribute="data-theme" defaultTheme="system" enableSystem storageKey="crackcms-theme">
            <TooltipProvider>
              <AuthProvider>
                <ExamTrackProvider>
                  <DockProvider>
                    <DatadogInit />
                    <Suspense fallback={null}>
                      <TrafficAnalytics />
                    </Suspense>
                    <BackendWarmup />
                    <main id="main-content">{children}</main>
                    <Footer />
                    <FloatingDock />
                    <WatermarkOverlay />
                    <StickyExamCta />
                  </DockProvider>
                </ExamTrackProvider>
              </AuthProvider>
            </TooltipProvider>
          </ThemeProvider>
        </PWAProvider>
      </body>
    </html>
  );
}
