'use client';

import { Flame, Target, Sparkles, Swords, Zap } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { RivalPayload } from '../types';

interface Props {
    rival: RivalPayload | null;
    meRank: number | null;
    meXp: number;
}

/**
 * Rival card. Shows the top real learner as the user's chase target.
 * No fabricated personas are ever rendered here — when the user-base is
 * small and no rival exists, the celebratory variant is rendered instead.
 */
export default function RivalCard({ rival, meRank, meXp }: Props) {
    // I'm already on top — celebratory variant.
    if (!rival || (meRank !== null && meRank <= 1)) {
        return (
            <Card className="border-amber-500/40 bg-gradient-to-br from-amber-500/15 via-card to-card relative overflow-hidden">
                <CardContent className="p-5 flex items-start gap-3">
                    <div className="shrink-0 w-10 h-10 rounded-2xl bg-amber-500/20 flex items-center justify-center">
                        <Sparkles className="w-5 h-5 text-amber-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <h3 className="font-bold text-foreground">You&apos;re #1 right now</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            No one ahead of you. Keep showing up — your streak is the longest streak on the platform.
                        </p>
                        <div className="flex items-center gap-1.5 mt-3 text-xs text-muted-foreground">
                            <Flame className="w-3.5 h-3.5 text-orange-500" />
                            <span>Your current streak: {meXp > 0 ? `🔥 ${Math.max(1, meXp)}` : '—'}</span>
                        </div>
                    </div>
                </CardContent>
            </Card>
        );
    }

    const ahead = rival.xp_to_surpass;
    const questions = rival.questions_to_surpass;

    return (
        <Card
            className="relative overflow-hidden border-rose-500/30 bg-gradient-to-br from-rose-500/10 via-card to-card"
            data-testid="rival-card"
        >
            <div
                className="absolute -top-12 -right-12 w-40 h-40 rounded-full bg-rose-500/10 blur-2xl pointer-events-none"
                aria-hidden="true"
            />
            <CardContent className="p-5 relative space-y-3">
                <div className="flex items-center gap-2">
                    <Swords className="w-5 h-5 text-rose-500" />
                    <h3 className="font-bold text-foreground">Surpass @{rival.username}</h3>
                    {rival.college && (
                        <Badge variant="outline" className="text-[10px] truncate max-w-45">
                            🎓 {rival.college}
                        </Badge>
                    )}
                </div>

                <div className="grid grid-cols-3 gap-2">
                    <Stat icon={<Zap className="w-3.5 h-3.5 text-yellow-500" />} label="Their XP" value={rival.xp_points.toLocaleString()} />
                    <Stat icon={<Flame className="w-3.5 h-3.5 text-orange-500" />} label="Streak" value={`${rival.current_streak}d`} />
                    <Stat icon={<Target className="w-3.5 h-3.5 text-emerald-500" />} label="Accuracy" value={`${rival.accuracy.toFixed(1)}%`} />
                </div>

                {ahead > 0 ? (
                    <div className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-sm">
                        <p className="font-semibold text-rose-600 dark:text-rose-300">
                            Solve {questions.toLocaleString()} more question{questions === 1 ? '' : 's'} to surpass @{rival.username}.
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                            That&apos;s <span className="font-bold text-foreground">{ahead.toLocaleString()} XP</span> to climb past their rank.
                        </p>
                    </div>
                ) : (
                    <p className="text-xs text-muted-foreground">
                        You&apos;re tied. Answer one more correctly to overtake them.
                    </p>
                )}
            </CardContent>
        </Card>
    );
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
    return (
        <div className="rounded-lg border border-border/60 bg-background/60 p-2 text-center">
            <div className="flex items-center justify-center gap-1 text-[9px] uppercase tracking-wider text-muted-foreground font-semibold">
                {icon}
                <span>{label}</span>
            </div>
            <div className="text-sm font-bold text-foreground mt-0.5">{value}</div>
        </div>
    );
}