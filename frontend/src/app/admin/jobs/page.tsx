'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { jobsAPI, questionsAPI } from '@/lib/api';
import { hasNextPage, listCount, listRows } from '../_lib/adminHelpers';
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
    const [jobsTotal, setJobsTotal] = useState(0);
    const [jobsNextPage, setJobsNextPage] = useState<number | null>(null);
    const [loadingMore, setLoadingMore] = useState(false);
    const [tracks, setTracks] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [deletingId, setDeletingId] = useState<number | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [formData, setFormData] = useState<JobForm>(EMPTY_FORM);

    // The jobs list is paginated (20 per page): page 1 replaces the list,
    // "Load more" appends the next page.
    const fetchJobs = useCallback(async (page = 1) => {
        if (page === 1) setLoading(true);
        else setLoadingMore(true);
        setError(null);
        try {
            const res = await jobsAPI.list({ page });
            const rows = listRows<any>(res.data);
            setJobs(prev => (page === 1 ? rows : [...prev, ...rows]));
            setJobsTotal(listCount(res.data));
            setJobsNextPage(hasNextPage(res.data) ? page + 1 : null);
        } catch (err) {
            console.error(err);
            setError('Could not load jobs. Check the API connection.');
        } finally {
            setLoading(false);
            setLoadingMore(false);
        }
    }, []);

    // Exam tracks for the target-track picker. Use centralized api.ts so base
    // URL failover (DigitalOcean primary + onrender.com blacklist) applies.
    // Falls back silently if the endpoint is unavailable — jobs work without it.
    const fetchTracks = useCallback(async () => {
        try {
            const trackRes = await questionsAPI.getExamTracks();
            setTracks(listRows<any>(trackRes.data));
        } catch {
            setTracks([]);
        }
    }, []);

    // Single load, after the admin gate. (A second unconditional effect used
    // to fetch everything again on every mount, even for non-admins.)
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
        fetchJobs(1);
        fetchTracks();
    }, [authLoading, user, isAdmin, router, fetchJobs, fetchTracks]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitting(true);
        setError(null);
        try {
            await jobsAPI.create({ ...formData, admin_edited: true });
            setFormData(EMPTY_FORM);
            await fetchJobs(1);
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
            // Drop it locally so rows already loaded with "Load more" stay.
            setJobs(prev => prev.filter(job => job.id !== id));
            setJobsTotal(total => Math.max(0, total - 1));
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
        <div className="p-4 sm:p-6 max-w-5xl mx-auto space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-bold flex items-center gap-2">
                        <Briefcase className="h-6 w-6" />
                        Job Postings
                    </h1>
                    <p className="text-sm text-muted-foreground mt-1">
                        Manage medical job postings shown to candidates.
                    </p>
                </div>
                <Button variant="outline" onClick={() => fetchJobs(1)} disabled={loading}>
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
                        Posted jobs appear on the candidate jobs board immediately and are never
                        overwritten by the job scraper.
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
                        {/* One checkbox per track: a <select multiple> needed
                            Ctrl/Cmd-click, which phones and the app don't have,
                            and showed no clear selected state. */}
                        <fieldset className="min-w-0 space-y-1">
                            <legend className="text-sm font-medium">Target Exam Tracks</legend>
                            {tracks.length === 0 ? (
                                <p className="text-xs text-muted-foreground">No exam tracks available.</p>
                            ) : (
                                <div className="grid grid-cols-1 gap-2 pt-1 sm:grid-cols-2">
                                    {tracks.map(t => {
                                        const trackId = Number(t.id);
                                        return (
                                            <label
                                                key={t.id}
                                                className="flex cursor-pointer items-center gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm"
                                            >
                                                <input
                                                    type="checkbox"
                                                    className="h-4 w-4 accent-primary"
                                                    checked={formData.exam_tracks.includes(trackId)}
                                                    onChange={(e) => {
                                                        const checked = e.target.checked;
                                                        setFormData(prev => ({
                                                            ...prev,
                                                            exam_tracks: checked
                                                                ? [...prev.exam_tracks.filter(id => id !== trackId), trackId]
                                                                : prev.exam_tracks.filter(id => id !== trackId),
                                                        }));
                                                    }}
                                                />
                                                {t.name}
                                            </label>
                                        );
                                    })}
                                </div>
                            )}
                        </fieldset>
                        <Button type="submit" disabled={submitting}>
                            {submitting ? 'Creating…' : 'Create Job'}
                        </Button>
                    </form>
                </CardContent>
            </Card>

            <Card>
                <CardHeader>
                    <CardTitle>Existing Jobs ({jobsTotal || jobs.length})</CardTitle>
                    <CardDescription>
                        Posted jobs visible on the candidate jobs board.
                        {jobsTotal > jobs.length && ` Showing ${jobs.length} of ${jobsTotal}.`}
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
                            {jobsNextPage !== null && (
                                <div className="flex justify-center pt-1">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => fetchJobs(jobsNextPage)}
                                        disabled={loadingMore}
                                    >
                                        {loadingMore ? 'Loading…' : 'Load more'}
                                    </Button>
                                </div>
                            )}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}