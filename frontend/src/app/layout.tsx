import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider } from "@/components/ThemeProvider";
import BackendWarmup from "@/components/BackendWarmup";
import { TooltipProvider } from "@/components/ui/tooltip";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "CrackCMS — UPSC CMS Preparation Platform",
  description: "India's most comprehensive AI-powered preparation platform for UPSC CMS. 3000+ PYQs, AI Tutor, Mock Tests, Analytics & more.",
  keywords: "UPSC CMS, medical exam, PYQ, AI tutor, preparation platform, CMS exam",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans antialiased`}>
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
