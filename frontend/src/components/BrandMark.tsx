"use client";

import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface BrandMarkProps {
  href?: string;
  compact?: boolean;
  light?: boolean;
  showTagline?: boolean;
  priority?: boolean;
  className?: string;
}

function BrandMarkContent({
  compact = false,
  light = false,
  showTagline = true,
  priority = false,
  className,
}: Omit<BrandMarkProps, "href">) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div
        className={cn(
          "relative overflow-hidden rounded-full border shadow-sm",
          compact ? "h-10 w-10" : "h-12 w-12",
          light
            ? "border-white/15 bg-white/10 shadow-black/10"
            : "border-border/70 bg-card/90 shadow-slate-900/5"
        )}
      >
        <Image
          src="/cms-circle-logo.png"
          alt="CrackCMS logo"
          fill
          priority={priority}
          className="object-cover"
          sizes={compact ? "40px" : "48px"}
        />
      </div>
      <div className="min-w-0">
        <p
          className={cn(
            "font-black leading-none tracking-[-0.04em]",
            compact ? "text-lg" : "text-xl",
            light ? "text-white" : "text-foreground"
          )}
        >
          CrackCMS
        </p>
        {showTagline ? (
          <p
            className={cn(
              "mt-1 text-[11px] font-medium uppercase tracking-[0.16em]",
              light ? "text-white/70" : "text-muted-foreground"
            )}
          >
            Doctor-first AI prep system
          </p>
        ) : null}
      </div>
    </div>
  );
}

export default function BrandMark({
  href,
  compact = false,
  light = false,
  showTagline = true,
  priority = false,
  className,
}: BrandMarkProps) {
  const content = (
    <BrandMarkContent
      compact={compact}
      light={light}
      showTagline={showTagline}
      priority={priority}
      className={className}
    />
  );

  if (!href) {
    return content;
  }

  return (
    <Link href={href} className="inline-flex">
      {content}
    </Link>
  );
}
