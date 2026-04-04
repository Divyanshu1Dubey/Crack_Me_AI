"use client";

import type { ReactNode } from "react";
import { Brain, Mail, ShieldCheck, Stethoscope } from "lucide-react";
import BrandMark from "@/components/BrandMark";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

interface AuthShellProps {
  badge: string;
  title: string;
  description: string;
  children: ReactNode;
  highlights?: string[];
  mode?: 'student' | 'admin';
}

const shellIcons = [ShieldCheck, Mail, Brain, Stethoscope];

export default function AuthShell({
  badge,
  title,
  description,
  children,
  highlights = [],
  mode = 'student',
}: AuthShellProps) {
  const bgGlow = mode === 'admin'
    ? 'bg-[radial-gradient(circle_at_top_left,rgba(180,83,9,0.10),transparent_38%),radial-gradient(circle_at_top_right,rgba(30,58,138,0.08),transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.72),transparent_100%)]'
    : 'bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.08),transparent_38%),radial-gradient(circle_at_top_right,rgba(15,23,42,0.04),transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.72),transparent_100%)]';

  const darkBgGlow = mode === 'admin'
    ? 'dark:bg-[radial-gradient(circle_at_top_left,rgba(245,158,11,0.14),transparent_34%),radial-gradient(circle_at_top_right,rgba(29,78,216,0.16),transparent_34%),linear-gradient(180deg,rgba(2,6,23,0.78),transparent_100%)]'
    : 'dark:bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.12),transparent_34%),radial-gradient(circle_at_top_right,rgba(15,23,42,0.16),transparent_34%),linear-gradient(180deg,rgba(2,6,23,0.78),transparent_100%)]';

  const orbColor = mode === 'admin' ? 'bg-amber-600/10' : 'bg-blue-600/5';

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center bg-slate-50 dark:bg-slate-950 px-4 py-8 sm:px-6 lg:px-8">
      <div className="pointer-events-none absolute inset-0">
        <div className={`absolute inset-x-0 top-0 h-[32rem] ${bgGlow} ${darkBgGlow}`} />
        <div className={`absolute left-1/2 top-24 h-80 w-80 -translate-x-1/2 rounded-full ${orbColor} blur-3xl p-1`} />
      </div>

      <div className="relative w-full max-w-[440px] z-10">
        <div className="mb-8 flex justify-center">
            <BrandMark href="/" priority className="scale-110" />
        </div>
        
        <Card className="border-border shadow-2xl bg-card">
          <CardContent className="p-6 sm:p-8">
            <div className="mb-8 text-center">
              <Badge variant="secondary" className="mb-4 rounded-full border border-border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.11em]">
                {badge}
              </Badge>
              <h2 className="text-2xl font-bold tracking-tight text-foreground">
                {title}
              </h2>
              <p className="mt-2 text-sm text-muted-foreground">
                {description}
              </p>

              {highlights.length > 0 && (
                <div className="mt-5 space-y-2 rounded-xl border border-border bg-muted/50 px-4 py-3 text-left">
                  {highlights.slice(0, 3).map((item, idx) => {
                    const Icon = shellIcons[idx % shellIcons.length];
                    return (
                      <div key={item} className="flex items-start gap-2 text-xs text-muted-foreground">
                        <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                        <span className="leading-relaxed">{item}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
            {children}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
