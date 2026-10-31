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
  Crown,
  PhoneCall,
  Briefcase,
  Clock,
  FileText,
  Flame,
  Circle,
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

const iconMap: Record<string, LucideIcon> = {
  'admin-shield': Shield,
  'ai-questions-creativity': Sparkles,
  'ai-tutor-brain': Brain,
  'analytics-growth': TrendingUp,
  'bookmarks-ribbon': BookMarked,
  'briefcase': Briefcase,
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
  'subscription-gold': Crown,
  'tests-check': ClipboardCheck,
  'textbooks-open-book': BookOpen,
  'trends-graph': Gauge,
  'upload-train': Upload,
  'contact-support': PhoneCall,
  // Used by the sidebar / dashboard but previously unmapped: they fell back
  // to /icons/custom/<name>.png files that do not exist (broken images).
  'book-open': BookOpen,
  'clock': Clock,
  'file-text': FileText,
  'flame': Flame,
};

export default function CustomIcon({
  name,
  label,
  className,
  size = 20,
  variant = 'default',
}: CustomIconProps) {
  const safeName = name.replace(/[^a-z0-9-_]+/gi, '').toLowerCase();
  // Every icon is rendered from lucide. The old PNG fallback pointed at
  // /icons/custom/<name>.png, and every PNG that exists already has a lucide
  // mapping above, so the fallback could only ever render a broken image.
  const IconComponent = iconMap[safeName] || Circle;

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
