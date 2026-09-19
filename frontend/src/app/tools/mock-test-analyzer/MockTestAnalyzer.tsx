"use client";

import { useState } from "react";

const DEFAULT_SUBJECTS = [
  "Preventive & Social Medicine",
  "General Medicine",
  "General Surgery",
  "Obstetrics & Gynaecology",
  "Paediatrics",
  "ENT",
  "Ophthalmology",
  "Orthopaedics",
  "Psychiatry",
  "Dermatology & Venereology",
  "Anaesthesiology",
  "Radiodiagnosis & Radiotherapy",
  "Pathology",
  "Pharmacology",
  "Microbiology",
];

type SubjectScores = Record<string, number>;

export default function MockTestAnalyzer() {
  const [subjectScores, setSubjectScores] = useState<SubjectScores>({});
  const [analysis, setAnalysis] = useState<{
    sortedSubjects: { subject: string; score: number }[];
    weakest: { subject: string; score: number }[];
    strongest: { subject: string; score: number }[];
    overallScore: number;
    totalQuestions: number;
    subjectsBelowThreshold: number;
    recommendation: string;
  } | null>(null);

  const handleScoreChange = (subject: string, value: string) => {
    const score = value === "" ? 0 : Math.max(0, Math.min(100, Number(value)));
    setSubjectScores((prev) => ({ ...prev, [subject]: score }));
  };

  const runAnalysis = () => {
    const filled = DEFAULT_SUBJECTS.filter((subject) => subjectScores[subject] !== undefined && subjectScores[subject] > 0);

    if (filled.length === 0) {
      setAnalysis({
        sortedSubjects: [],
        weakest: [],
        strongest: [],
        overallScore: 0,
        totalQuestions: 0,
        subjectsBelowThreshold: 0,
        recommendation: "Enter at least one subject score to analyze your mock test performance.",
      });
      return;
    }

    const subjects = filled.map((subject) => ({
      subject,
      score: subjectScores[subject],
    }));

    subjects.sort((a, b) => a.score - b.score);

    const overallScore = Math.round(subjects.reduce((sum, s) => sum + s.score, 0) / subjects.length);
    const belowThreshold = subjects.filter((s) => s.score < 60).length;
    const weakest = subjects.slice(0, 3);
    const strongest = subjects.slice(-3).reverse();

    let recommendation = "";
    if (overallScore >= 80) {
      recommendation =
        "Excellent overall performance. Focus on maintaining consistency and fine-tuning weak areas before the exam.";
    } else if (overallScore >= 60) {
      recommendation =
        "Solid baseline. Prioritize the weakest subjects identified below and revise key concepts with focused PYQ practice.";
    } else if (overallScore >= 40) {
      recommendation =
        "Significant improvement needed. Build a structured revision plan for the weakest subjects and take additional sectional mock tests.";
    } else {
      recommendation =
        "Foundational gaps detected. Start with core textbooks for the weakest subjects, then move to question-bank drills before attempting full mocks.";
    }

    setAnalysis({
      sortedSubjects: subjects,
      weakest,
      strongest,
      overallScore,
      totalQuestions: filled.length,
      subjectsBelowThreshold: belowThreshold,
      recommendation,
    });
  };

  const resetForm = () => {
    setSubjectScores({});
    setAnalysis(null);
  };

  return (
    <div className="mx-auto w-full max-w-5xl">
      <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
        <h2 className="text-2xl font-bold text-foreground">Enter Your Mock Test Scores</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Input your subject-wise percentage scores from recent mock tests. Leave unused subjects blank.
        </p>

        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {DEFAULT_SUBJECTS.map((subject) => (
            <label key={subject} className="flex flex-col gap-1">
              <span className="text-sm font-medium text-foreground">{subject}</span>
              <input
                type="number"
                min={0}
                max={100}
                placeholder="0 - 100"
                value={subjectScores[subject] ?? ""}
                onChange={(e) => handleScoreChange(subject, e.target.value)}
                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </label>
          ))}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <button
            onClick={runAnalysis}
            className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
          >
            Analyze Performance
          </button>
          <button
            onClick={resetForm}
            className="rounded-xl border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
          >
            Reset
          </button>
        </div>
      </div>

      {analysis && (
        <div className="mt-8 space-y-8">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border border-border bg-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Overall Score</p>
              <p className="mt-2 text-3xl font-black text-foreground">{analysis.overallScore}%</p>
              <p className="mt-1 text-xs text-muted-foreground">Across {analysis.totalQuestions} subjects</p>
            </div>
            <div className="rounded-2xl border border-border bg-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Weak Subjects</p>
              <p className="mt-2 text-3xl font-black text-red-500">{analysis.subjectsBelowThreshold}</p>
              <p className="mt-1 text-xs text-muted-foreground">Scoring below 60%</p>
            </div>
            <div className="rounded-2xl border border-border bg-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Weakest Area</p>
              <p className="mt-2 text-xl font-bold text-foreground">{analysis.weakest[0]?.subject ?? "N/A"}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Score: {analysis.weakest[0]?.score ?? "—"}%
              </p>
            </div>
            <div className="rounded-2xl border border-border bg-card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Strongest Area</p>
              <p className="mt-2 text-xl font-bold text-foreground">{analysis.strongest[0]?.subject ?? "N/A"}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Score: {analysis.strongest[0]?.score ?? "—"}%
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-card p-6 sm:p-8">
            <h3 className="text-xl font-bold text-foreground">Subject-wise Performance</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Sorted from weakest to strongest to help you prioritize revision.
            </p>
            <div className="mt-4 space-y-3">
              {analysis.sortedSubjects.map((item) => {
                const color = item.score >= 80 ? "bg-green-500" : item.score >= 60 ? "bg-amber-500" : "bg-red-500";
                return (
                  <div key={item.subject} className="flex items-center gap-4">
                    <span className="min-w-[220px] text-sm font-medium text-foreground">{item.subject}</span>
                    <div className="flex-1 h-3 rounded-full bg-muted/50">
                      <div
                        className={`h-3 rounded-full ${color}`}
                        style={{ width: `${Math.min(100, item.score)}%` }}
                      />
                    </div>
                    <span className="w-12 text-right text-sm font-semibold text-foreground">{item.score}%</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-muted/50 p-6 sm:p-8">
            <h3 className="text-xl font-bold text-foreground">Recommendation</h3>
            <p className="mt-2 text-sm text-foreground">{analysis.recommendation}</p>
          </div>
        </div>
      )}
    </div>
  );
}
