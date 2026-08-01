'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { jobsAPI, questionsAPI } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Trash2, Briefcase, MapPin, IndianRupee, ExternalLink, Plus } from 'lucide-react';

/**
 * /admin/jobs — full CRUD UI for the `jobs.Job` model (medical job
 * postings). Reachable directly via the URL or via the "Jobs" tile on
 * the admin dashboard, which deep-links here.
 *
 * The page is intentionally self-contained: list, create, delete all
 * live here with no modals so the create flow is fast for the daily
 * "post 5 hospital jobs" use case.
 */
interface JobForm {
    title: string;
    hospital: string;
    location: string;
    description: string;
    eligibility_summary: string;
    exam_tracks: number[];
    apply_link: string;
    salary: string;
}

const EMPTY_FORM: JobForm = {
    title: '',
    hospital: '',
    location: '',
    description: '',
    eligibility_summary: '',
    exam_tracks: [],
    apply_link: '',
    salary: '',
};

export default function AdminJobsPage() {
    const { user, loading: authLoading } = useAuth();
    const router = useRouter();
    // Client-side admin gate (backend `IsAdminUser` is the authoritative RBAC).
    const isAdmin = !!user && (user.role === 'admin' || user.is_admin);

    const [jobs, setJobs] = useState<any[]>([]);
    const [tracks, setTracks] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [deletingId, setDeletingId] = useState<number | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [formData, setFormData] = useState<JobForm>(EMPTY_FORM);

    const fetchJobs = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await jobsAPI.list();
            const rows = res.data.results || res.data || [];
            setJobs(Array.isArray(rows) ? rows : []);
            // Use centralized api.ts so base URL failover (DigitalOcean primary
            // + onrender.com blacklist) applies. Falls back silently if the
            // exam-tracks endpoint is unavailable — jobs work fine without it.
            try {
                const trackRes = await questionsAPI.getExamTracks();
                const trackData = trackRes.data?.results || trackRes.data || [];
                setTracks(Array.isArray(trackData) ? trackData : []);
            } catch {
                setTracks([]);
            }
        } catch (err) {
            console.error(err);
            setError('Could not load jobs. Check the API connection.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        if (authLoading) return;
        if (!user) {
            router.replace('/login?next=' + encodeURIComponent('/admin/jobs'));
            return;
        }
        if (!isAdmin) {
            router.replace('/dashboard');
            return;
        }
        fetchJobs();
    }, [authLoading, user, isAdmin, router, fetchJobs]);

    useEffect(() => {
        fetchJobs();
    }, [fetchJobs]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitting(true);
        setError(null);
        try {
            await jobsAPI.create({ ...formData, admin_edited: true });
            setFormData(EMPTY_FORM);
            await fetchJobs();
        } catch (err) {
            console.error(err);
            setError('Error creating job. Verify all fields are valid.');
        } finally {
            setSubmitting(false);
        }
    };

    const handleDelete = async (id: number) => {
        if (!confirm('Are you sure you want to delete this job?')) return;
        setDeletingId(id);
        try {
            await jobsAPI.remove(id);
            await fetchJobs();
        } catch (err) {
            console.error(err);
            setError('Could not delete job.');
        } finally {
            setDeletingId(null);
        }
    };

    const trackName = (id: number) => tracks.find(t => t.id === id)?.name ?? `#${id}`;

    if (authLoading || !user) {
        return (
            <div className="flex items-center justify-center min-h-[60vh] text-muted-foreground">
                Checking admin access…
            </div>
        );
    }

    if (!isAdmin) {
        return null;
    }

    return (
        <div className="p-6 max-w-5xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <Briefcase className="h-6 w-6" />
                        Job Postings
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Manage medical job postings shown to candidates.
                    </p>
                </div>
                <Button variant="outline" onClick={fetchJobs} disabled={loading}>
                    {loading ? 'Refreshing…' : 'Refresh'}
                </Button>
            </div>

            {error && (
                <div className="rounded-md border border-red-500 bg-red-50 dark:bg-red-950/30 p-3 text-sm text-red-700 dark:text-red-300">
                    {error}
                </div>
            )}

            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Plus className="h-4 w-4" />
                        Create New Job
                    </CardTitle>
                    <CardDescription>
                        Posted jobs appear on the candidate jobs board immediately. Set{' '}
                        <code>admin_edited=true</code> (set automatically) so the scraper
                        never overwrites them.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <label className="text-sm font-medium">Job Title</label>
                                <Input
                                    required
                                    value={formData.title}
                                    onChange={e => setFormData({ ...formData, title: e.target.value })}
                                    placeholder="Senior Resident — Cardiology"
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-medium">Hospital / Organization</label>
                                <Input
                                    required
                                    value={formData.hospital}
                                    onChange={e => setFormData({ ...formData, hospital: e.target.value })}
                                    placeholder="AIIMS New Delhi"
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-medium">Location</label>
                                <Input
                                    required
                                    value={formData.location}
                                    onChange={e => setFormData({ ...formData, location: e.target.value })}
                                    placeholder="New Delhi, India"
                                />
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-medium">Salary (optional)</label>
                                <Input
                                    value={formData.salary}
                                    onChange={e => setFormData({ ...formData, salary: e.target.value })}
                                    placeholder="₹1,20,000 / month"
                                />
                            </div>
                            <div className="space-y-1 md:col-span-2">
                                <label className="text-sm font-medium">Application Link</label>
                                <Input
                                    required
                                    type="url"
                                    value={formData.apply_link}
                                    onChange={e => setFormData({ ...formData, apply_link: e.target.value })}
                                    placeholder="https://example.com/apply"
                                />
                            </div>
                        </div>
                        <div className="space-y-1">
                            <label className="text-sm font-medium">Description</label>
                            <textarea
                                required
                                rows={3}
                                value={formData.description}
                                onChange={e => setFormData({ ...formData, description: e.target.value })}
                                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                placeholder="Role summary, duties, contract length…"
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-sm font-medium">Eligibility Summary</label>
                            <textarea
                                required
                                rows={2}
                                value={formData.eligibility_summary}
                                onChange={e => setFormData({ ...formData, eligibility_summary: e.target.value })}
                                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                placeholder="MBBS + MS/MD in Cardiology; MCI registration required"
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-sm font-medium">Target Exam Tracks</label>
                            <select
                                multiple
                                value={formData.exam_tracks.map(String)}
                                onChange={(e) => {
                                    const selected = Array.from(
                                        e.target.selectedOptions,
                                        option => parseInt(option.value),
                                    );
                                    setFormData({ ...formData, exam_tracks: selected });
                                }}
                                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-24 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            >
                                {tracks.map(t => (
                                    <option key={t.id} value={t.id} className="p-1">{t.name}</option>
                                ))}
                            </select>
                            <p className="text-xs text-muted-foreground">
                                Hold Ctrl/Cmd to select multiple.
                            </p>
                        </div>
                        <Button type="submit" disabled={submitting}>
                            {submitting ? 'Creating…' : 'Create Job'}
                        </Button>
                    </form>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Existing Jobs ({jobs.length})</CardTitle>
                    <CardDescription>
                        Posted jobs visible on the candidate jobs board.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <p className="text-sm text-muted-foreground py-4">Loading…</p>
                    ) : jobs.length === 0 ? (
                        <p className="text-sm text-muted-foreground py-4">
                            No jobs posted yet. Create one above.
                        </p>
                    ) : (
                        <div className="space-y-3">
                            {jobs.map(job => (
                                <div
                                    key={job.id}
                                    className="flex flex-col md:flex-row md:items-start md:justify-between gap-3 p-4 border rounded-lg bg-muted/20"
                                >
                                    <div className="space-y-1 min-w-0">
                                        <h3 className="font-semibold">{job.title} <span className="text-muted-foreground font-normal">at {job.hospital}</span></h3>
                                        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                                            <span className="flex items-center gap-1">
                                                <MapPin className="h-3 w-3" />
                                                {job.location}
                                            </span>
                                            {job.salary && (
                                                <span className="flex items-center gap-1">
                                                    <IndianRupee className="h-3 w-3" />
                                                    {job.salary}
                                                </span>
                                            )}
                                            <a
                                                href={job.apply_link}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="flex items-center gap-1 hover:underline"
                                            >
                                                <ExternalLink className="h-3 w-3" />
                                                Apply link
                                            </a>
                                        </div>
                                        {Array.isArray(job.exam_tracks) && job.exam_tracks.length > 0 && (
                                            <div className="flex gap-1 mt-1 flex-wrap">
                                                {job.exam_tracks.map((trackId: number) => (
                                                    <Badge key={trackId} variant="secondary">
                                                        {trackName(trackId)}
                                                    </Badge>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                    <Button
                                        size="sm"
                                        variant="destructive"
                                        disabled={deletingId === job.id}
                                        onClick={() => handleDelete(job.id)}
                                        className="self-start"
                                    >
                                        <Trash2 className="h-3 w-3 mr-1" />
                                        {deletingId === job.id ? 'Deleting…' : 'Delete'}
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}