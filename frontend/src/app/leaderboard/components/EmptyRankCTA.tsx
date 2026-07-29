'use client';

import { ArrowRight, Sparkles } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Card, CardContent } from '@/components/ui/card';

/**
 * Rendered when the requesting user has 0 XP and no rank.
 *
 * No fabricated motivator ("Join 500+ …"). Just a single, honest CTA:
 * answer one question to appear on the board.
 */
export default function EmptyRankCTA() {
    const router = useRouter();
    return (
        <Card className="border-primary/30 bg-gradient-to-br from-primary/10 via-card to-card">
            <CardContent className="p-8 md:p-10 text-center flex flex-col items-center gap-3">
                <div className="w-14 h-14 rounded-2xl bg-primary/15 flex items-center justify-center">
                    <Sparkles className="w-7 h-7 text-primary" />
                </div>
                <h2 className="text-xl font-bold text-foreground">You&apos;re unranked — answer 1 question to enter the board</h2>
                <p className="text-sm text-muted-foreground max-w-md">
                    Pick a topic, take a few questions, and your XP will start climbing. We&apos;ll show you a real
                    learner to chase — never a fake name.
                </p>
                <button
                    type="button"
                    onClick={() => router.push('/questions')}
                    className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 font-semibold text-sm px-5 py-2.5 transition-colors"
                >
                    Practice Questions
                    <ArrowRight className="w-4 h-4" />
                </button>
            </CardContent>
        </Card>
    );
}