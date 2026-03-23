"use client";

import type { ReactNode } from "react";
import { ArrowRight, Brain, Mail, ShieldCheck, Stethoscope } from "lucide-react";
import BrandMark from "@/components/BrandMark";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

interface AuthShellProps {
  badge: string;
  title: string;
  description: string;
  children: ReactNode;
  highlights?: string[];
}

const shellIcons = [ShieldCheck, Mail, Brain, Stethoscope];

export default function AuthShell({
  title,
  description,
  children,
}: AuthShellProps) {
  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center bg-slate-50 dark:bg-slate-950 px-4 py-8 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-x-0 top-0 h-[32rem] bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.08),transparent_38%),radial-gradient(circle_at_top_right,rgba(15,23,42,0.04),transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.72),transparent_100%)] dark:bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.12),transparent_34%),radial-gradient(circle_at_top_right,rgba(15,23,42,0.16),transparent_34%),linear-gradient(180deg,rgba(2,6,23,0.78),transparent_100%)]" />
        <div className="absolute left-1/2 top-24 h-80 w-80 -translate-x-1/2 rounded-full bg-blue-600/5 blur-3xl p-1" />
      </div>

      <div className="relative w-full max-w-[440px] z-10">
        <div className="mb-8 flex justify-center">
            <BrandMark href="/" priority className="scale-110" />
        </div>
        
        <Card className="border-border shadow-2xl bg-card">
          <CardContent className="p-6 sm:p-8">
            <div className="mb-8 text-center">
              <h2 className="text-2xl font-bold tracking-tight text-foreground">
                {title}
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                {description}
              </p>
            </div>
            {children}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
