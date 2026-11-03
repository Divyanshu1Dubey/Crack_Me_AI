/**
 * Pure logic for the PYQ Attempt Analyzer (kept import-free so it can be
 * unit-tested with Node).
 *
 * Input: one "Topic, correct, total" row per line. Overall accuracy is
 * sum(correct) / sum(total) — it used to divide the summed correct answers
 * by the number of LINES, so 8/10, 6/8, 5/7, 9/10 showed 700% instead of 80%.
 */

export interface TopicScore {
    topic: string;
    correct: number;
    total: number;
    accuracy: number;
}

export interface AttemptAnalysis {
    accuracy: number;
    totalCorrect: number;
    totalQuestions: number;
    topics: TopicScore[];
    mastered: string[];
    needsWork: string[];
    /** Lines that could not be read (wrong format, total of 0, ...). */
    skippedLines: number;
}

export const MASTERED_THRESHOLD = 75;
export const NEEDS_WORK_THRESHOLD = 50;

export function analyzePyqAttempts(text: string): AttemptAnalysis {
    const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
    const byTopic = new Map<string, { topic: string; correct: number; total: number }>();
    let skippedLines = 0;

    for (const line of lines) {
        const parts = line.split(',').map((p) => p.trim());
        if (parts.length < 3 || !parts[0]) {
            skippedLines += 1;
            continue;
        }
        const correct = Number.parseInt(parts[1], 10);
        const total = Number.parseInt(parts[2], 10);
        if (!Number.isFinite(correct) || !Number.isFinite(total) || total <= 0 || correct < 0) {
            skippedLines += 1;
            continue;
        }
        const key = parts[0].toLowerCase();
        const entry = byTopic.get(key) ?? { topic: parts[0], correct: 0, total: 0 };
        // A row cannot have more correct answers than questions.
        entry.correct += Math.min(correct, total);
        entry.total += total;
        byTopic.set(key, entry);
    }

    const topics: TopicScore[] = Array.from(byTopic.values()).map((t) => ({
        ...t,
        accuracy: Math.round((t.correct / t.total) * 100),
    }));
    const totalCorrect = topics.reduce((acc, t) => acc + t.correct, 0);
    const totalQuestions = topics.reduce((acc, t) => acc + t.total, 0);

    return {
        accuracy: totalQuestions > 0 ? Math.round((totalCorrect / totalQuestions) * 100) : 0,
        totalCorrect,
        totalQuestions,
        topics,
        mastered: topics.filter((t) => t.accuracy >= MASTERED_THRESHOLD).map((t) => t.topic),
        needsWork: topics.filter((t) => t.accuracy < NEEDS_WORK_THRESHOLD).map((t) => t.topic),
        skippedLines,
    };
}
