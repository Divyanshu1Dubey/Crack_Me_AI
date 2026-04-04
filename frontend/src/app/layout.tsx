import type { Metadata } from "next";
import { Manrope, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/components/ThemeProvider";
import BackendWarmup from "@/components/BackendWarmup";
import { TooltipProvider } from "@/components/ui/tooltip";

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://www.cracklabs.app";
const siteTitle = "CrackCMS | UPSC CMS Preparation Platform";
const siteDescription =
  "Doctor-first UPSC CMS preparation platform with PYQs, AI tutoring, analytics, and adaptive test workflows for serious medical aspirants.";

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
    template: "%s | CrackCMS",
  },
  description: siteDescription,
  applicationName: "CrackCMS",
  keywords: [
    "UPSC CMS",
    "medical exam preparation",
    "UPSC CMS PYQ",
    "UPSC CMS mock tests",
    "AI tutor for medical students",
    "CrackCMS",
  ],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    type: "website",
    url: siteUrl,
    title: siteTitle,
    description: siteDescription,
    siteName: "CrackCMS",
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
      <body className={`${manrope.variable} ${spaceGrotesk.variable} font-sans antialiased`}>
        <ThemeProvider attribute="data-theme" defaultTheme="light" enableSystem>
          <TooltipProvider>
            <AuthProvider>
              <BackendWarmup />
              {children}
            </AuthProvider>
          </TooltipProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
