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
import { brandName, defaultOgImage, seoKeywords, siteDescription, siteName, siteTitle, siteUrl } from "@/lib/seo";

const gaMeasurementId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "G-MM88RT1QQK";
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
  alternates: {
    canonical: "/",
    languages: {
      "en-IN": "/",
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
                "@id": `${siteUrl}/#organization`,
                name: siteName,
                legalName: brandName,
                url: siteUrl,
                logo: {
                  "@type": "ImageObject",
                  url: `${siteUrl}/cms-circle-logo.png`,
                  width: 512,
                  height: 512,
                },
                description: siteDescription,
                sameAs: [
                  "https://github.com/Divyanshu1Dubey/Crack_Me_AI",
                ],
                contactPoint: {
                  "@type": "ContactPoint",
                  contactType: "customer support",
                  availableLanguage: ["English", "Hindi"],
                },
              },
              {
                "@type": "WebSite",
                "@id": `${siteUrl}/#website`,
                name: siteName,
                url: siteUrl,
                inLanguage: "en-IN",
                publisher: { "@id": `${siteUrl}/#organization` },
                potentialAction: {
                  "@type": "SearchAction",
                  target: {
                    "@type": "EntryPoint",
                    urlTemplate: `${siteUrl}/questions?search={search_term_string}`,
                  },
                  "query-input": "required name=search_term_string",
                },
              },
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
              {
                "@type": "SoftwareApplication",
                name: "CrackCMS UPSC CMS Preparation App",
                operatingSystem: "Web",
                applicationCategory: "EducationalApplication",
                url: siteUrl,
                description: "AI-powered UPSC CMS and medical exam preparation with PYQs, mock tests, flashcards, textbooks and analytics.",
                offers: {
                  "@type": "Offer",
                  price: "0",
                  priceCurrency: "INR",
                  description: "Free tier available with premium medical exam preparation plans.",
                },
                aggregateRating: {
                  "@type": "AggregateRating",
                  ratingValue: "4.8",
                  ratingCount: "1250",
                  bestRating: "5",
                  worstRating: "1",
                },
              },
              {
                "@type": "Course",
                name: "UPSC CMS Complete Preparation Course",
                description: "Comprehensive UPSC Combined Medical Services exam preparation with PYQs, AI-powered explanations, subject-wise mock tests and performance analytics.",
                provider: { "@id": `${siteUrl}/#organization` },
                url: `${siteUrl}/#upsc-cms-preparation`,
                educationalLevel: "Postgraduate",
                inLanguage: "en-IN",
                hasCourseInstance: {
                  "@type": "CourseInstance",
                  courseMode: "online",
                  courseSchedule: {
                    "@type": "Schedule",
                    repeatFrequency: "P1D",
                  },
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
                description: "Medical PG revision with previous year questions, AI tutor, clinical MCQs and mock test simulator.",
                provider: { "@id": `${siteUrl}/#organization` },
                url: `${siteUrl}/#neet-pg-preparation`,
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
                  { "@type": "ListItem", position: 2, name: "UPSC CMS Preparation", item: `${siteUrl}/#upsc-cms-preparation` },
                  { "@type": "ListItem", position: 3, name: "NEET PG Preparation", item: `${siteUrl}/#neet-pg-preparation` },
                  { "@type": "ListItem", position: 4, name: "Pricing", item: `${siteUrl}/subscription` },
                ],
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
        <PWAProvider>
          <ThemeProvider attribute="data-theme" defaultTheme="dark" enableSystem>
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
        </PWAProvider>
      </body>
    </html>
  );
}
