'use client';
import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { topicNotesAPI } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { BookOpen, Sparkles, Plus, Trash2, FileText } from 'lucide-react';
import { useRouter } from 'next/navigation';

interface TopicNote {
    id: number;
    title: string;
    content: string;
    subject: number;
    subject_name: string;
    topic: number;
    topic_name: string;
    exam_type: string;
    is_ai_generated: boolean;
    source_question_count: number;
    created_at: string;
    updated_at: string;
}

export default function TopicNotesPage() {
    const { user } = useAuth();
    const router = useRouter();
    const [notes, setNotes] = useState<TopicNote[]>([]);
    const [loading, setLoading] = useState(true);
    const [showCreate, setShowCreate] = useState(false);
    const [generatingId, setGeneratingId] = useState<number | null>(null);
    const [formData, setFormData] = useState({
        subject: '',
        topic: '',
        exam_type: 'cms',
        title: '',
        content: '',
        source_question_ids: '',
    });

    useEffect(() => {
        topicNotesAPI.adminList().then(res => {
            setNotes(res.data as TopicNote[]);
            setLoading(false);
        }).catch(() => setLoading(false));
    }, []);

    const handleCreate = async () => {
        if (!formData.title || !formData.subject || !formData.topic) return;
        try {
            const res = await topicNotesAPI.adminCreate({
                subject: parseInt(formData.subject),
                topic: parseInt(formData.topic),
                exam_type: formData.exam_type,
                title: formData.title,
                content: formData.content,
                source_question_ids: formData.source_question_ids
                    ? formData.source_question_ids.split(',').map(Number).filter(Boolean)
                    : [],
            });
            setNotes(prev => [...prev, res.data as TopicNote]);
            setFormData({ subject: '', topic: '', exam_type: 'cms', title: '', content: '', source_question_ids: '' });
            setShowCreate(false);
        } catch (err) {
            console.error('Create note failed:', err);
        }
    };

    const handleGenerate = async (id: number) => {
        setGeneratingId(id);
        try {
            const res = await topicNotesAPI.adminGenerate(id);
            setNotes(prev => prev.map(n =>
                n.id === id ? { ...n, ...res.data, is_ai_generated: true } : n
            ));
        } catch (err) {
            console.error('Generate note failed:', err);
        } finally {
            setGeneratingId(null);
        }
    };

    if (loading) {
        return (
            <div className="max-w-4xl mx-auto p-6 space-y-4">
                <Skeleton className="h-8 w-48" />
                {[1, 2, 3].map(i => <Skeleton key={i} className="h-40" />)}
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto p-4 md:p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-emerald-100 dark:bg-emerald-900/30 rounded-lg">
                        <BookOpen className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold">Topic Notes</h1>
                        <p className="text-sm text-muted-foreground">
                            AI-generated revision notes from PYQ explanations
                        </p>
                    </div>
                </div>
                <Button onClick={() => setShowCreate(!showCreate)} size="sm">
                    <Plus className="w-4 h-4 mr-1" />
                    New Note
                </Button>
            </div>

            {/* Create Form */}
            {showCreate && (
                <Card className="border-primary/20">
                    <CardHeader>
                        <CardTitle className="text-lg">Create Topic Note</CardTitle>
                        <CardDescription>
                            Compile PYQ explanations into revision notes
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            <div>
                                <label className="text-sm font-medium">Subject ID</label>
                                <input
                                    type="number"
                                    className="w-full mt-1 p-2 border rounded-md text-sm"
                                    value={formData.subject}
                                    onChange={e => setFormData(f => ({ ...f, subject: e.target.value }))}
                                    placeholder="e.g. 1"
                                />
                            </div>
                            <div>
                                <label className="text-sm font-medium">Topic ID</label>
                                <input
                                    type="number"
                                    className="w-full mt-1 p-2 border rounded-md text-sm"
                                    value={formData.topic}
                                    onChange={e => setFormData(f => ({ ...f, topic: e.target.value }))}
                                    placeholder="e.g. 15"
                                />
                            </div>
                            <div>
                                <label className="text-sm font-medium">Exam</label>
                                <select
                                    className="w-full mt-1 p-2 border rounded-md text-sm"
                                    value={formData.exam_type}
                                    onChange={e => setFormData(f => ({ ...f, exam_type: e.target.value }))}
                                >
                                    <option value="cms">UPSC CMS</option>
                                    <option value="neet_pg">NEET PG</option>
                                    <option value="ini_cet">INI-CET</option>
                                </select>
                            </div>
                        </div>
                        <div>
                            <label className="text-sm font-medium">Title</label>
                            <input
                                type="text"
                                className="w-full mt-1 p-2 border rounded-md text-sm"
                                value={formData.title}
                                onChange={e => setFormData(f => ({ ...f, title: e.target.value }))}
                                placeholder="e.g. Nephrology - Glomerular Diseases"
                            />
                        </div>
                        <div>
                            <label className="text-sm font-medium">Content</label>
                            <textarea
                                className="w-full mt-1 p-2 border rounded-md text-sm h-32"
                                value={formData.content}
                                onChange={e => setFormData(f => ({ ...f, content: e.target.value }))}
                                placeholder="Write or paste note content here..."
                            />
                        </div>
                        <div>
                            <label className="text-sm font-medium">Source Question IDs (comma-separated)</label>
                            <input
                                type="text"
                                className="w-full mt-1 p-2 border rounded-md text-sm"
                                value={formData.source_question_ids}
                                onChange={e => setFormData(f => ({ ...f, source_question_ids: e.target.value }))}
                                placeholder="e.g. 123, 456, 789"
                            />
                        </div>
                        <div className="flex gap-2">
                            <Button onClick={handleCreate} size="sm">Create Note</Button>
                            <Button variant="outline" onClick={() => setShowCreate(false)} size="sm">Cancel</Button>
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Notes List */}
            {notes.length === 0 ? (
                <Card>
                    <CardContent className="p-8 text-center text-muted-foreground">
                        <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
                        <p>No topic notes yet. Create one or generate from corrected PYQs.</p>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-3">
                    {notes.map(note => (
                        <Card key={note.id}>
                            <CardContent className="p-4">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h3 className="font-semibold">{note.title}</h3>
                                            <Badge variant="outline" className="text-xs capitalize">
                                                {note.exam_type}
                                            </Badge>
                                            {note.is_ai_generated && (
                                                <Badge className="text-xs bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                                                    <Sparkles className="w-3 h-3 mr-1" />
                                                    AI
                                                </Badge>
                                            )}
                                        </div>
                                        <p className="text-sm text-muted-foreground line-clamp-3">
                                            {note.content}
                                        </p>
                                        <div className="text-xs text-muted-foreground mt-2">
                                            {note.topic_name || `Topic ${note.topic}`} • {note.source_question_count} source Qs
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                        {!note.is_ai_generated && (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => handleGenerate(note.id)}
                                                disabled={generatingId === note.id}
                                            >
                                                <Sparkles className="w-3 h-3 mr-1" />
                                                {generatingId === note.id ? 'Generating...' : 'Generate'}
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
