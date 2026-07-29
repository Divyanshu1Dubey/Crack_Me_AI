'use client';

import { Check, Copy, MessageCircle, Share2 } from 'lucide-react';
import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import type { InvitePayload } from '../types';

interface Props {
    invite: InvitePayload;
}

/**
 * Soft invite gate. Always visible until `live_board_enabled` is true.
 * Provides copy / WhatsApp / X (Twitter) share actions. No DB writes —
 * the URL simply carries `?ref=<user_id>` so a future Referral model can
 * attribute signups without changing this component.
 */
export default function InviteGate({ invite }: Props) {
    const [copied, setCopied] = useState(false);

    const onCopy = async () => {
        if (typeof navigator === 'undefined' || !navigator.clipboard) return;
        try {
            await navigator.clipboard.writeText(invite.url);
            setCopied(true);
            setTimeout(() => setCopied(false), 1800);
        } catch {
            // Older browsers / denied permission: silently no-op.
        }
    };

    const shareText = encodeURIComponent(
        `Studying for UPSC CMS on CrackCMS — join me: ${invite.url}`,
    );
    const whatsappHref = `https://wa.me/?text=${shareText}`;
    const twitterHref = `https://twitter.com/intent/tweet?text=${shareText}`;

    return (
        <Card className="border-cyan-500/30 bg-gradient-to-br from-cyan-500/8 via-card to-card">
            <CardContent className="p-5 space-y-4">
                <div className="flex items-start gap-3">
                    <div className="shrink-0 w-10 h-10 rounded-2xl bg-cyan-500/15 flex items-center justify-center">
                        <Share2 className="w-5 h-5 text-cyan-500" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <h3 className="font-bold text-foreground">Compete with peers</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                            {invite.cta}. Invite 2 friends to unlock the live leaderboard for everyone.
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2 p-2.5 rounded-lg border border-border bg-muted/40">
                    <code className="flex-1 text-xs font-mono truncate text-foreground" aria-label="Invite URL">
                        {invite.url}
                    </code>
                </div>

                <div className="flex flex-wrap gap-2">
                    <button
                        type="button"
                        onClick={onCopy}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-700 text-white text-xs font-semibold px-3 py-2 transition-colors"
                        aria-label="Copy invite link"
                    >
                        {copied ? (
                            <>
                                <Check className="w-3.5 h-3.5" />
                                Copied
                            </>
                        ) : (
                            <>
                                <Copy className="w-3.5 h-3.5" />
                                Copy invite link
                            </>
                        )}
                    </button>
                    <a
                        href={whatsappHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-3 py-2 transition-colors"
                        aria-label="Share on WhatsApp"
                    >
                        <MessageCircle className="w-3.5 h-3.5" />
                        WhatsApp
                    </a>
                    <a
                        href={twitterHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-slate-800 dark:hover:bg-slate-700 text-white text-xs font-semibold px-3 py-2 transition-colors"
                        aria-label="Share on X / Twitter"
                    >
                        <Share2 className="w-3.5 h-3.5" />
                        X / Twitter
                    </a>
                </div>

                <p className="text-[11px] text-muted-foreground leading-relaxed">
                    No spam, no email harvesting. Your invite link just adds <code className="font-mono">?ref=&lt;you&gt;</code> to the signup URL.
                </p>
            </CardContent>
        </Card>
    );
}