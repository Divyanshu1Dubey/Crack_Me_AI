/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { useEffect, useState } from 'react';
import { discussionsAPI } from '@/lib/api';
import { MessageSquare, ThumbsUp, ThumbsDown, Send, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface Discussion {
    id: number;
    user_name: string;
    text: string;
    upvotes: number;
    downvotes: number;
    reply_count: number;
    user_vote: 'up' | 'down' | null;
    is_pinned: boolean;
    created_at: string;
}

export default function DiscussionThread({ questionId }: { questionId: number }) {
    const [discussions, setDiscussions] = useState<Discussion[]>([]);
    const [loading, setLoading] = useState(true);
    const [newComment, setNewComment] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [expanded, setExpanded] = useState(false);
    const [replies, setReplies] = useState<Record<number, Discussion[]>>({});
    const [replyTo, setReplyTo] = useState<number | null>(null);
    const [replyText, setReplyText] = useState('');

    useEffect(() => {
        setExpanded(false);
        setDiscussions([]);
        setLoading(true);
        discussionsAPI.list(questionId)
            .then(res => {
                const data = Array.isArray(res.data) ? res.data : res.data?.results || [];
                setDiscussions(data);
            })
            .catch(() => setDiscussions([]))
            .finally(() => setLoading(false));
    }, [questionId]);

    const handlePost = async () => {
        if (!newComment.trim()) return;
        setSubmitting(true);
        try {
            const res = await discussionsAPI.create({ question: questionId, text: newComment });
            setDiscussions([res.data, ...discussions]);
            setNewComment('');
        } catch { /* ignore */ }
        setSubmitting(false);
    };

    const handleReply = async (parentId: number) => {
        if (!replyText.trim()) return;
        setSubmitting(true);
        try {
            const res = await discussionsAPI.create({ question: questionId, text: replyText, parent: parentId });
            setReplies({ ...replies, [parentId]: [...(replies[parentId] || []), res.data] });
            setReplyText('');
            setReplyTo(null);
            // Update reply count
            setDiscussions(discussions.map(d => d.id === parentId ? { ...d, reply_count: d.reply_count + 1 } : d));
        } catch { /* ignore */ }
        setSubmitting(false);
    };

    const handleVote = async (id: number, voteType: 'up' | 'down') => {
        try {
            const res = await discussionsAPI.vote(id, voteType);
            setDiscussions(discussions.map(d => d.id === id ? { ...d, upvotes: res.data.upvotes, downvotes: res.data.downvotes, user_vote: res.data.user_vote } : d));
        } catch { /* ignore */ }
    };

    const loadReplies = async (id: number) => {
        try {
            const res = await discussionsAPI.replies(id);
            const data = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setReplies({ ...replies, [id]: data });
        } catch { /* ignore */ }
    };

    const [now, setNow] = useState(Date.now());

    useEffect(() => {
        const interval = setInterval(() => setNow(Date.now()), 60000);
        return () => clearInterval(interval);
    }, []);

    const timeAgo = (dateStr: string) => {
        const diff = now - new Date(dateStr).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 60) return `${mins}m ago`;
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return `${hrs}h ago`;
        const days = Math.floor(hrs / 24);
        return `${days}d ago`;
    };

    return (
        <div className="mt-4 border-t pt-4">
            <button
                onClick={() => setExpanded(!expanded)}
                className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors w-full"
            >
                <MessageSquare className="w-4 h-4" />
                <span>Discussion ({discussions.length})</span>
                {expanded ? <ChevronUp className="w-4 h-4 ml-auto" /> : <ChevronDown className="w-4 h-4 ml-auto" />}
            </button>

            {expanded && (
                <div className="mt-3 space-y-3">
                    {/* Post new */}
                    <div className="flex gap-2">
                        <input
                            type="text"
                            className="flex-1 rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            placeholder="Share your thoughts on this question..."
                            value={newComment}
                            onChange={e => setNewComment(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handlePost()}
                        />
                        <Button size="sm" onClick={handlePost} disabled={submitting || !newComment.trim()}>
                            <Send className="w-4 h-4" />
                        </Button>
                    </div>

                    {loading ? (
                        <p className="text-xs text-muted-foreground animate-pulse">Loading...</p>
                    ) : discussions.length === 0 ? (
                        <p className="text-xs text-muted-foreground text-center py-3">No comments yet. Be the first!</p>
                    ) : (
                        <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
                            {discussions.map(d => (
                                <div key={d.id} className={`rounded-lg border p-3 ${d.is_pinned ? 'border-primary/30 bg-primary/5' : ''}`}>
                                    <div className="flex items-center gap-2 mb-1">
                                        <div className="w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center text-[10px] font-bold text-primary">
                                            {d.user_name?.charAt(0)?.toUpperCase() || '?'}
                                        </div>
                                        <span className="text-xs font-medium">{d.user_name}</span>
                                        <span className="text-[10px] text-muted-foreground">{timeAgo(d.created_at)}</span>
                                        {d.is_pinned && <Badge variant="outline" className="text-[9px] px-1">Pinned</Badge>}
                                    </div>
                                    <p className="text-sm leading-relaxed mb-2">{d.text}</p>
                                    <div className="flex items-center gap-3 text-xs">
                                        <button
                                            onClick={() => handleVote(d.id, 'up')}
                                            className={`flex items-center gap-1 transition-colors ${d.user_vote === 'up' ? 'text-emerald-500' : 'text-muted-foreground hover:text-emerald-500'}`}
                                        >
                                            <ThumbsUp className="w-3.5 h-3.5" /> {d.upvotes}
                                        </button>
                                        <button
                                            onClick={() => handleVote(d.id, 'down')}
                                            className={`flex items-center gap-1 transition-colors ${d.user_vote === 'down' ? 'text-red-500' : 'text-muted-foreground hover:text-red-500'}`}
                                        >
                                            <ThumbsDown className="w-3.5 h-3.5" /> {d.downvotes}
                                        </button>
                                        <button
                                            onClick={() => {
                                                if (replyTo === d.id) { setReplyTo(null); }
                                                else { setReplyTo(d.id); if (!replies[d.id]) loadReplies(d.id); }
                                            }}
                                            className="text-muted-foreground hover:text-foreground transition-colors"
                                        >
                                            <MessageSquare className="w-3.5 h-3.5 inline mr-0.5" />
                                            {d.reply_count > 0 ? `${d.reply_count} replies` : 'Reply'}
                                        </button>
                                    </div>

                                    {/* Replies */}
                                    {replyTo === d.id && (
                                        <div className="mt-2 pl-4 border-l-2 border-muted space-y-2">
                                            {replies[d.id]?.map(r => (
                                                <div key={r.id} className="rounded p-2 bg-muted/50">
                                                    <div className="flex items-center gap-1.5 mb-0.5">
                                                        <span className="text-[11px] font-medium">{r.user_name}</span>
                                                        <span className="text-[10px] text-muted-foreground">{timeAgo(r.created_at)}</span>
                                                    </div>
                                                    <p className="text-xs leading-relaxed">{r.text}</p>
                                                </div>
                                            ))}
                                            <div className="flex gap-2">
                                                <input
                                                    type="text"
                                                    className="flex-1 rounded border bg-background px-2 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                                                    placeholder="Write a reply..."
                                                    value={replyText}
                                                    onChange={e => setReplyText(e.target.value)}
                                                    onKeyDown={e => e.key === 'Enter' && handleReply(d.id)}
                                                />
                                                <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => handleReply(d.id)} disabled={submitting || !replyText.trim()}>
                                                    Reply
                                                </Button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
