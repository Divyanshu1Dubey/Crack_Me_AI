'use client';
import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { studyTimeAPI } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Clock, TrendingUp, Calendar, Award } from 'lucide-react';

interface StudySession {
    id: number;
    subject: number;
    subject_name: string;
    seconds: number;
    question_count: number;
    date: string;
}

export default function StudyTimePage() {
    const { user } = useAuth();
    const [sessions, setSessions] = useState<StudySession[]>([]);
    const [summary, setSummary] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [recording, setRecording] = useState(false);

    useEffect(() => {
        studyTimeAPI.list().then(res => {
            setSessions(res.data as StudySession[]);
            setLoading(false);
        }).catch(() => setLoading(false));
    }, []);

    const formatDuration = (seconds: number) => {
        const hrs = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        if (hrs > 0) return `${hrs}h ${mins}m`;
        return `${mins}m`;
    };

    if (loading) {
        return (
            <div className="max-w-4xl mx-auto p-6 space-y-4">
                <Skeleton className="h-8 w-48" />
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-24" />)}
                </div>
                {[1, 2, 3].map(i => <Skeleton key={i} className="h-16" />)}
            </div>
        );
    }

    const totalSeconds = sessions.reduce((sum, s) => sum + s.seconds, 0);
    const totalQuestions = sessions.reduce((sum, s) => sum + s.question_count, 0);

    return (
        <div className="max-w-4xl mx-auto p-4 md:p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                    <Clock className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold">Study Time</h1>
                    <p className="text-sm text-muted-foreground">Track your daily study hours</p>
                </div>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Card>
                    <CardContent className="p-4 text-center">
                        <Clock className="w-5 h-5 text-blue-500 mx-auto mb-1" />
                        <div className="text-xl font-bold">{formatDuration(totalSeconds)}</div>
                        <div className="text-xs text-muted-foreground">Total Study Time</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="p-4 text-center">
                        <TrendingUp className="w-5 h-5 text-green-500 mx-auto mb-1" />
                        <div className="text-xl font-bold">{totalQuestions}</div>
                        <div className="text-xs text-muted-foreground">Questions Solved</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="p-4 text-center">
                        <Calendar className="w-5 h-5 text-purple-500 mx-auto mb-1" />
                        <div className="text-xl font-bold">{sessions.length}</div>
                        <div className="text-xs text-muted-foreground">Study Sessions</div>
                    </CardContent>
                </Card>
                <Card>
                    <CardContent className="p-4 text-center">
                        <Award className="w-5 h-5 text-amber-500 mx-auto mb-1" />
                        <div className="text-xl font-bold">
                            {sessions.length > 0 ? formatDuration(Math.round(totalSeconds / sessions.length)) : '0m'}
                        </div>
                        <div className="text-xs text-muted-foreground">Avg Session</div>
                    </CardContent>
                </Card>
            </div>

            {/* Session List */}
            {sessions.length === 0 ? (
                <Card>
                    <CardContent className="p-8 text-center text-muted-foreground">
                        <Clock className="w-12 h-12 mx-auto mb-3 opacity-30" />
                        <p>No study sessions recorded yet. Start practicing to track your time!</p>
                    </CardContent>
                </Card>
            ) : (
                <div className="space-y-2">
                    {sessions.map(session => (
                        <Card key={session.id}>
                            <CardContent className="p-4 flex items-center justify-between">
                                <div>
                                    <div className="font-medium">{session.subject_name || `Subject ${session.subject}`}</div>
                                    <div className="text-sm text-muted-foreground">
                                        {new Date(session.date).toLocaleDateString()} • {session.question_count} questions
                                    </div>
                                </div>
                                <Badge variant="secondary" className="text-sm">
                                    {formatDuration(session.seconds)}
                                </Badge>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
