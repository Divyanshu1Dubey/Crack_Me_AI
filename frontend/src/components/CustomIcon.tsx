import Image from 'next/image';
import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  BookOpen,
  BookMarked,
  Brain,
  ClipboardCheck,
  FolderOpen,
  Gauge,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Shield,
  Sparkles,
  Stethoscope,
  Target,
  TrendingUp,
  Trophy,
  Upload,
} from 'lucide-react';

interface CustomIconProps {
  name: string;
  label?: string;
  className?: string;
  size?: number;
  variant?: 'default' | 'active' | 'subtle';
}

const variantClasses: Record<NonNullable<CustomIconProps['variant']>, string> = {
  default: 'opacity-95 text-muted-foreground',
  active: 'opacity-100 text-primary',
  subtle: 'opacity-75 text-muted-foreground',
};

const imageVariantClasses: Record<NonNullable<CustomIconProps['variant']>, string> = {
  default: 'opacity-95',
  active: 'opacity-100 saturate-150',
  subtle: 'opacity-75',
};

const iconMap: Record<string, LucideIcon> = {
  'admin-shield': Shield,
  'ai-questions-creativity': Sparkles,
  'ai-tutor-brain': Brain,
  'analytics-growth': TrendingUp,
  'bookmarks-ribbon': BookMarked,
  'dashboard-layout': LayoutDashboard,
  'feedback-chat': MessageCircle,
  'flashcards-cards': GraduationCap,
  'leaderboard-trophy': Trophy,
  'logout-exit': LogOut,
  'medical-stethoscope': Stethoscope,
  'question-bank-book': BookOpen,
  'resources-folder': FolderOpen,
  'simulator-target': Target,
  'study-roadmap-map': Activity,
  'tests-check': ClipboardCheck,
  'textbooks-open-book': BookOpen,
  'trends-graph': Gauge,
  'upload-train': Upload,
};

export default function CustomIcon({
  name,
  label,
  className,
  size = 20,
  variant = 'default',
}: CustomIconProps) {
  const safeName = name.replace(/[^a-z0-9-_]+/gi, '').toLowerCase();
  const src = `/icons/custom/${safeName}.png`;
  const IconComponent = iconMap[safeName];

  if (IconComponent) {
    return (
      <span
        className={cn('inline-flex shrink-0 items-center justify-center', variantClasses[variant], className)}
        style={{ width: size, height: size }}
        {...(label ? { role: 'img' as const, 'aria-label': label } : { 'aria-hidden': true as const })}
      >
        <IconComponent className="h-full w-full" aria-hidden="true" />
      </span>
    );
  }

  return (
    <span className={cn('relative inline-flex shrink-0', className)} style={{ width: size, height: size }}>
      <Image
        src={src}
        alt={label || safeName.replace(/-/g, ' ')}
        fill
        sizes={`${size}px`}
        className={cn('object-contain', imageVariantClasses[variant])}
      />
    </span>
  );
}
