import type { Metadata } from "next";
import { Manrope, Plus_Jakarta_Sans } from "next/font/google";
import Script from "next/script";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/components/ThemeProvider";
import { brandName, defaultOgImage, seoKeywords, siteDescription, siteName, siteTitle, siteUrl } from "@/lib/seo";

const gaMeasurementId = process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || "";
const analyticsInDev = process.env.NEXT_PUBLIC_ANALYTICS_IN_DEV === "true";
const shouldInjectGoogleTag = Boolean(gaMeasurementId) && (process.env.NODE_ENV === "production" || analyticsInDev);

const manrope = Manrope({
    subsets: ["latin", "latin-ext"],
    variable: "--font-manrope",
    display: "swap",
});

const jakarta = Plus_Jakarta_Sans({
    subsets: ["latin", "latin-ext"],
    variable: "--font-jakarta",
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
        images: [{ url: defaultOgImage, width: 1200, height: 630, alt: "CrackFMGE — FMGE preparation" }],
    },
    twitter: { card: "summary_large_image", title: siteTitle, description: siteDescription, images: [defaultOgImage] },
    manifest: "/manifest.json",
    icons: { icon: [{ url: "/fmge-logo.png", type: "image/png" }] },
};

export const viewport = {
    width: "device-width",
    initialScale: 1,
    minimumScale: 1,
    maximumScale: 5,
    userScalable: true,
    themeColor: "#d97706",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
    return (
        <html lang="en" data-track="fmge" suppressHydrationWarning>
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
            <body className={`${manrope.variable} ${jakarta.variable} font-sans antialiased`}>
                <ThemeProvider attribute="data-theme" defaultTheme="system" enableSystem storageKey="crackfmge-theme">
                    <AuthProvider>{children}</AuthProvider>
                </ThemeProvider>
            </body>
        </html>
    );
}
