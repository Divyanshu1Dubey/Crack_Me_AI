import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/components/ThemeProvider";
import { brandName, defaultOgImage, seoKeywords, siteDescription, siteName, siteTitle, siteUrl } from "@/lib/seo";

const gaMeasurementId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "";
const analyticsInDev = process.env.NEXT_PUBLIC_ANALYTICS_IN_DEV === "true";
const shouldInjectGoogleTag = Boolean(gaMeasurementId) && (process.env.NODE_ENV === "production" || analyticsInDev);

const inter = Inter({
    subsets: ["latin", "latin-ext"],
    variable: "--font-inter",
    display: "swap",
});

const spaceGrotesk = Space_Grotesk({
    subsets: ["latin", "latin-ext"],
    variable: "--font-space-grotesk",
    display: "swap",
});

export const metadata: Metadata = {
    metadataBase: new URL(siteUrl),
    title: { default: siteTitle, template: `%s | ${siteName}` },
    description: siteDescription,
    keywords: seoKeywords,
    openGraph: {
        type: "website",
        url: siteUrl,
        title: siteTitle,
        description: siteDescription,
        siteName,
        images: [{ url: defaultOgImage, width: 1200, height: 630, alt: "CrackUSMLE — USMLE Step 1, 2 CK & 3" }],
    },
    twitter: { card: "summary_large_image", title: siteTitle, description: siteDescription, images: [defaultOgImage] },
    manifest: "/manifest.json",
    icons: { icon: [{ url: "/usmle-logo.png", type: "image/png" }] },
};

export const viewport = {
    width: "device-width",
    initialScale: 1,
    minimumScale: 1,
    maximumScale: 5,
    userScalable: true,
    themeColor: "#7c3aed",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
    return (
        <html lang="en" data-track="usmle" suppressHydrationWarning>
            <head>
                {shouldInjectGoogleTag && (
                    <>
                        <Script id="google-tag-src" src={`https://www.googletagmanager.com/gtag/js?id=${gaMeasurementId}`} strategy="beforeInteractive" />
                        <Script id="google-tag-inline" strategy="beforeInteractive">
                            {`window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('js',new Date());gtag('config','${gaMeasurementId}',{send_page_view:false});`}
                        </Script>
                    </>
                )}
            </head>
            <body className={`${inter.variable} ${spaceGrotesk.variable} font-sans antialiased`}>
                <ThemeProvider attribute="data-theme" defaultTheme="system" enableSystem storageKey="crackusmle-theme">
                    <AuthProvider>{children}</AuthProvider>
                </ThemeProvider>
            </body>
        </html>
    );
}
