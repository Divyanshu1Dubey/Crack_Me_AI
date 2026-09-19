'use client';

import { useState } from 'react';

export default function PyqAttemptAnalyzer() {
    const [attempts, setAttempts] = useState('');
    const [subject, setSubject] = useState('');
    const [result, setResult] = useState<{ accuracy: number; mastered: string[]; needsWork: string[] } | null>(null);

    const analyzeAttempts = () => {
        const lines = attempts.split('\n').filter(line => line.trim());
        const total = lines.length;
        let correct = 0;

        const topicScores: Record<string, { correct: number; total: number }> = {};

        lines.forEach(line => {
            const parts = line.split(',').map(p => p.trim());
            if (parts.length >= 3) {
                const topic = parts[0];
                const topicCorrect = parseInt(parts[1]) || 0;
                const topicTotal = parseInt(parts[2]) || 1;
                if (!topicScores[topic]) topicScores[topic] = { correct: 0, total: 0 };
                topicScores[topic].correct += topicCorrect;
                topicScores[topic].total += topicTotal;
                correct += topicCorrect;
            }
        });

        const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;
        const mastered: string[] = [];
        const needsWork: string[] = [];

        Object.entries(topicScores).forEach(([topic, scores]) => {
            const topicAccuracy = Math.round((scores.correct / scores.total) * 100);
            if (topicAccuracy >= 75) {
                mastered.push(topic);
            } else if (topicAccuracy < 50) {
                needsWork.push(topic);
            }
        });

        setResult({ accuracy, mastered, needsWork });
    };

    return (
        <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-bold">PYQ Attempt Analyzer</h3>
            <p className="mt-2 text-sm text-muted-foreground">
                Analyze your previous year question performance. Enter topic, correct count, and total questions attempted.
            </p>

            <div className="mt-6 space-y-5">
                <div>
                    <label className="block text-sm font-semibold mb-1">PYQ Attempts (one per line)</label>
                    <p className="text-xs text-muted-foreground mb-2">Format: Topic Name, Correct Count, Total Questions</p>
                    <textarea
                        value={attempts}
                        onChange={(e) => setAttempts(e.target.value)}
                        className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm font-mono"
                        rows={8}
                        placeholder="Cardiology, 8, 10&#10;Neurology, 6, 8&#10;Surgery, 5, 7&#10;..."
                    />
                </div>

                <button onClick={analyzeAttempts} className="w-full rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition hover:opacity-90">
                    Analyze Performance
                </button>

                {result && (
                    <div className="mt-6 space-y-4">
                        <div className="rounded-xl border border-border bg-muted/50 p-5">
                            <p className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">Overall Accuracy</p>
                            <p className="text-4xl font-black text-foreground mt-1">{result.accuracy}%</p>
                        </div>

                        {result.mastered.length > 0 && (
                            <div className="rounded-xl border border-green-500/40 bg-green-50 dark:bg-green-950/30 p-5">
                                <p className="text-sm font-bold text-green-700 dark:text-green-400 mb-2">Mastered Topics (≥75%)</p>
                                <ul className="space-y-1">
                                    {result.mastered.map((t, i) => (
                                        <li key={i} className="text-sm text-green-700 dark:text-green-300">✓ {t}</li>
                                    ))}
                                </ul>
                            </div>
                        )}

                        {result.needsWork.length > 0 && (
                            <div className="rounded-xl border border-red-500/40 bg-red-50 dark:bg-red-950/30 p-5">
                                <p className="text-sm font-bold text-red-700 dark:text-red-400 mb-2">Needs Improvement (<50%)</p>
                                <ul className="space-y-1">
                                    {result.needsWork.map((t, i) => (
                                        <li key={i} className="text-sm text-red-700 dark:text-red-300">✗ {t}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
