'use client';
import { Suspense, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { jobsAPI } from '@/lib/api';
import { Briefcase, MapPin, Building2, Clock, Search, ExternalLink, Bookmark } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

interface Job {
    id: number;
    title: string;
    hospital: string;
    location: string;
    category_name: string;
    description: string;
    salary: string;
    apply_link: string;
    posted_at: string;
    expires_at: string;
    is_bookmarked: boolean;
}

export default function JobsPage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen bg-background">
                    <Sidebar />
                    <div className="main-content">
                        <Header />
                        <div className="flex h-[50vh] items-center justify-center">
                            <div className="flex flex-col items-center gap-4">
                                <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                                <p className="text-muted-foreground">Loading Jobs Portal...</p>
                            </div>
                        </div>
                    </div>
                </div>
            }
        >
            <JobsContent />
        </Suspense>
    );
}

function JobsContent() {
    const { isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const [jobs, setJobs] = useState<Job[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [page, setPage] = useState(1);
    const [hasMore, setHasMore] = useState(true);
    const [examTrack, setExamTrack] = useState('all');

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push('/login');
            return;
        }
        if (isAuthenticated) {
            fetchJobs(1, true);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [authLoading, isAuthenticated, router]);

    const fetchJobs = async (pageNum: number, isInitial = false) => {
        try {
            if (isInitial) setLoading(true);
            const params: Record<string, string | number> = { page: pageNum, page_size: 15 };
            if (searchQuery) params.search = searchQuery;
            if (examTrack !== 'all') params.exam_track = examTrack;
            const res = await jobsAPI.list(params);
            const results = res.data.results || res.data || [];
            
            if (isInitial) {
                setJobs(results);
            } else {
                setJobs(prev => [...prev, ...results]);
            }
            
            setHasMore(!!res.data.next);
            setPage(pageNum);
        } catch (error) {
            console.error('Failed to fetch jobs:', error);
        } finally {
            if (isInitial) setLoading(false);
        }
    };

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        fetchJobs(1, true);
    };

    const toggleBookmark = async (jobId: number) => {
        try {
            await jobsAPI.bookmark(jobId);
            setJobs(prev => prev.map(job => 
                job.id === jobId ? { ...job, is_bookmarked: !job.is_bookmarked } : job
            ));
        } catch (error) {
            console.error('Failed to bookmark job:', error);
        }
    };

    return (
        <div className="min-h-screen bg-background">
            <Sidebar />
            <div className="main-content">
                <Header />

                <div className="mb-6 space-y-4">
                    <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
                            <Briefcase className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold tracking-tight text-foreground">Medical Jobs Portal</h1>
                            <p className="text-sm text-muted-foreground">Find medical officer, resident, and specialized roles</p>
                        </div>
                    </div>

                    <form onSubmit={handleSearch} className="flex flex-col sm:flex-row max-w-3xl gap-3">
                        <div className="relative flex-1">
                            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                            <Input 
                                placeholder="Search by title, hospital, or location..." 
                                className="pl-9 h-11 bg-card border-border/80"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                        </div>
                        <select 
                            className="h-11 px-4 rounded-xl border border-border/80 bg-card text-sm"
                            value={examTrack}
                            onChange={(e) => setExamTrack(e.target.value)}
                        >
                            <option value="all">All Tracks</option>
                            <option value="cms">UPSC CMS</option>
                            <option value="neet_pg">NEET PG</option>
                            <option value="fmge">FMGE</option>
                            <option value="usmle">USMLE</option>
                        </select>
                        <Button type="submit" className="h-11 px-8 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground transition-all">
                            Search
                        </Button>
                    </form>
                </div>

                <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
                    {loading ? (
                        Array.from({ length: 6 }).map((_, i) => (
                            <Card key={i} className="border-border/60 bg-card/50">
                                <CardContent className="p-5 space-y-4">
                                    <Skeleton className="h-6 w-3/4" />
                                    <Skeleton className="h-4 w-1/2" />
                                    <div className="space-y-2">
                                        <Skeleton className="h-4 w-full" />
                                        <Skeleton className="h-4 w-5/6" />
                                    </div>
                                </CardContent>
                            </Card>
                        ))
                    ) : jobs.length === 0 ? (
                        <div className="col-span-full py-12 text-center">
                            <Briefcase className="mx-auto h-12 w-12 text-muted-foreground/30 mb-3" />
                            <h3 className="text-lg font-medium text-foreground">No jobs found</h3>
                            <p className="text-muted-foreground">Try adjusting your search criteria</p>
                        </div>
                    ) : (
                        jobs.map(job => (
                            <Card key={job.id} className="group relative border-border/80 bg-card transition-all hover:border-primary/30 hover:shadow-md">
                                <CardContent className="p-5">
                                    <div className="flex justify-between items-start gap-4 mb-3">
                                        <h3 className="font-semibold text-lg leading-tight text-foreground group-hover:text-primary transition-colors">
                                            {job.title}
                                        </h3>
                                        <button 
                                            onClick={() => toggleBookmark(job.id)}
                                            className="shrink-0 p-2 -mr-2 -mt-2 rounded-full hover:bg-muted transition-colors"
                                        >
                                            <Bookmark className={`h-4 w-4 ${job.is_bookmarked ? 'fill-primary text-primary' : 'text-muted-foreground'}`} />
                                        </button>
                                    </div>

                                    <div className="space-y-2 mb-4">
                                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                            <Building2 className="h-4 w-4 shrink-0 text-muted-foreground/70" />
                                            <span className="truncate">{job.hospital}</span>
                                        </div>
                                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                            <MapPin className="h-4 w-4 shrink-0 text-muted-foreground/70" />
                                            <span className="truncate">{job.location}</span>
                                        </div>
                                        {job.salary && (
                                            <div className="flex items-center gap-2 text-sm font-medium text-emerald-600 dark:text-emerald-400">
                                                <span className="truncate">{job.salary}</span>
                                            </div>
                                        )}
                                    </div>

                                    <div className="flex items-center justify-between mt-6 pt-4 border-t border-border/50">
                                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                                            <Clock className="h-3.5 w-3.5" />
                                            <span>Posted {new Date(job.posted_at).toLocaleDateString()}</span>
                                        </div>
                                        <Button 
                                            asChild 
                                            size="sm" 
                                            className="h-8 rounded-lg bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground transition-all"
                                        >
                                            <a href={job.apply_link} target="_blank" rel="noopener noreferrer">
                                                Apply <ExternalLink className="ml-1.5 h-3 w-3" />
                                            </a>
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        ))
                    )}
                </div>

                {!loading && hasMore && (
                    <div className="mt-8 text-center">
                        <Button 
                            variant="outline" 
                            onClick={() => fetchJobs(page + 1)}
                            className="rounded-xl border-border bg-card hover:bg-accent"
                        >
                            Load More Jobs
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
}
