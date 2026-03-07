import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/components/ThemeProvider";
import BackendWarmup from "@/components/BackendWarmup";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "CrackCMS — AI-Powered UPSC CMS Preparation Platform",
  description: "The most advanced AI-powered preparation platform for UPSC CMS with PYQ engine, AI tutor, mnemonic generator, and performance analytics.",
  keywords: "UPSC CMS, medical exam, PYQ, AI tutor, preparation platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} antialiased`}>
        <ThemeProvider attribute="data-theme" defaultTheme="dark" enableSystem>
          <AuthProvider>
            <BackendWarmup />
            {children}
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
