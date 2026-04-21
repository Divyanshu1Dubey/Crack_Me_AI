/* eslint-disable @typescript-eslint/no-explicit-any */
'use client';
import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import { analyticsAPI, authAPI, questionsAPI, testsAPI, textbooksAPI } from '@/lib/api';
import {
    Users, BookOpen, FileText, AlertTriangle, TrendingUp,
    CheckCircle, Clock, Shield, Megaphone, Plus, Trash2,
    Zap, MessageSquare, Gift, FileSearch, ShieldCheck,
    Database, BarChart3, Sparkles, Wallet
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';

interface DashboardData {
    total_users: number;
    active_today: number;
    total_questions: number;
    questions_with_answer: number;
    questions_with_explanation: number;
    answer_percentage: number;
    total_tests_taken: number;
    unresolved_feedback: number;
    recent_signups: { id: number; username: string; date_joined: string }[];
}

interface Announcement {
    id: number;
    title: string;
    message: string;
    priority: string;
    is_active: boolean;
    is_expired: boolean;
    created_at: string;
    expires_at: string | null;
}

const priorityColors: Record<string, string> = {
    low: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
    normal: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
    high: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
    urgent: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
};

type AdminTabKey =
    | 'overview'
    | 'users'
    | 'feedback'
    | 'questions'
    | 'tests'
    | 'textbooks'
    | 'analytics'
    | 'moderation'
    | 'broadcast'
    | 'security'
    | 'audit'
    | 'finance'
    | 'ai';

export default function AdminDashboardPage() {
    const { user, isAuthenticated, loading: authLoading } = useAuth();
    const router = useRouter();
    const hasAdminAccess = user?.role === 'admin' || user?.is_admin;
    const [data, setData] = useState<DashboardData | null>(null);
    const [announcements, setAnnouncements] = useState<Announcement[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState({ title: '', message: '', priority: 'normal', expires_at: '' });
    const [submitting, setSubmitting] = useState(false);
    const [activeTab, setActiveTab] = useState<AdminTabKey>('overview');
    const [adminSearch, setAdminSearch] = useState('');
    const [adminFilter, setAdminFilter] = useState('all');
    // Users & token management
    const [userList, setUserList] = useState<any[]>([]);
    const [usersLoading, setUsersLoading] = useState(false);
    const [grantUserId, setGrantUserId] = useState('');
    const [grantAmount, setGrantAmount] = useState('');
    const [grantNote, setGrantNote] = useState('');
    const [granting, setGranting] = useState(false);
    const [grantMsg, setGrantMsg] = useState('');
    const [userSearchTerm, setUserSearchTerm] = useState('');
    const [userRoleFilter, setUserRoleFilter] = useState('all');
    const [userStatusFilter, setUserStatusFilter] = useState('all');
    const [userActionLoadingId, setUserActionLoadingId] = useState<number | null>(null);
    const [userActionMessage, setUserActionMessage] = useState('');
    const [systemScope, setSystemScope] = useState<'all' | 'user'>('all');
    const [systemUserId, setSystemUserId] = useState('');
    const [systemActionLoading, setSystemActionLoading] = useState(false);
    // Feedback queue
    const [feedbackList, setFeedbackList] = useState<any[]>([]);
    const [feedbackLoading, setFeedbackLoading] = useState(false);
    // Question bank control
    const [questionList, setQuestionList] = useState<any[]>([]);
    const [questionsLoading, setQuestionsLoading] = useState(false);
    const [questionSubjects, setQuestionSubjects] = useState<any[]>([]);
    const [questionTopics, setQuestionTopics] = useState<any[]>([]);
    const [questionPage, setQuestionPage] = useState(1);
    const [questionTotal, setQuestionTotal] = useState(0);
    const [questionHasNext, setQuestionHasNext] = useState(false);
    const [questionSearch, setQuestionSearch] = useState('');
    const [questionSubject, setQuestionSubject] = useState('');
    const [questionDifficulty, setQuestionDifficulty] = useState('');
    const [questionYear, setQuestionYear] = useState('');
    const [questionAccuracyMin, setQuestionAccuracyMin] = useState('');
    const [questionAccuracyMax, setQuestionAccuracyMax] = useState('');
    const [questionVerified, setQuestionVerified] = useState('all');
    const [questionFlagged, setQuestionFlagged] = useState('all');
    const [showAdvancedQuestionFilters, setShowAdvancedQuestionFilters] = useState(false);
    const [compactQuestionPreview, setCompactQuestionPreview] = useState(true);
    const [expandedQuestionIds, setExpandedQuestionIds] = useState<number[]>([]);
    const [selectedQuestionIds, setSelectedQuestionIds] = useState<number[]>([]);
    const [bulkActionLoading, setBulkActionLoading] = useState(false);
    const [editingQuestionId, setEditingQuestionId] = useState<number | null>(null);
    const [editingForm, setEditingForm] = useState({
        question_text: '',
        option_a: '',
        option_b: '',
        option_c: '',
        option_d: '',
        correct_answer: '',
        explanation: '',
        difficulty: 'medium',
        year: '',
        subject: '',
        topic: '',
        paper: '',
        concept_id: '',
        book_name: '',
        chapter: '',
        page_number: '',
        reference_text: '',
        related_question_ids: '',
    });
    const [savingEdit, setSavingEdit] = useState(false);
    const [createForm, setCreateForm] = useState({
        question_text: '',
        option_a: '',
        option_b: '',
        option_c: '',
        option_d: '',
        correct_answer: 'A',
        year: '',
        subject: '',
        topic: '',
        paper: '',
        difficulty: 'medium',
        explanation: '',
        concept_id: '',
        book_name: '',
        chapter: '',
        page_number: '',
        reference_text: '',
        related_question_ids: '',
    });
    const [createLoading, setCreateLoading] = useState(false);
    const [importFormat, setImportFormat] = useState<'json' | 'csv'>('json');
    const [importPayload, setImportPayload] = useState('');
    const [importPreviewLoading, setImportPreviewLoading] = useState(false);
    const [importPreviewResult, setImportPreviewResult] = useState<any | null>(null);
    const [bulkMetaSubject, setBulkMetaSubject] = useState('');
    const [bulkMetaTopic, setBulkMetaTopic] = useState('');
    const [bulkMetaDifficulty, setBulkMetaDifficulty] = useState('');
    const [bulkMetaYear, setBulkMetaYear] = useState('');
    const [bulkMetaPaper, setBulkMetaPaper] = useState('');
    const [bulkMetaLoading, setBulkMetaLoading] = useState(false);
    const [bulkDeleteConfirm, setBulkDeleteConfirm] = useState('');
    const [bulkDeleteLoading, setBulkDeleteLoading] = useState(false);
    const [extractionFile, setExtractionFile] = useState<File | null>(null);
    const [extractionLoading, setExtractionLoading] = useState(false);
    const [extractionJobs, setExtractionJobs] = useState<any[]>([]);
    const [extractionJobsLoading, setExtractionJobsLoading] = useState(false);
    const [selectedExtractionJobId, setSelectedExtractionJobId] = useState<number | null>(null);
    const [extractionItems, setExtractionItems] = useState<any[]>([]);
    const [extractionItemsLoading, setExtractionItemsLoading] = useState(false);
    const [editingExtractionItemId, setEditingExtractionItemId] = useState<number | null>(null);
    const [editingExtractionItem, setEditingExtractionItem] = useState<any>(null);
    const [aiPromptVersions, setAiPromptVersions] = useState<any[]>([]);
    const [aiPromptName, setAiPromptName] = useState('Default Prompt');
    const [aiPromptText, setAiPromptText] = useState('Generate clear, exam-oriented answer and explanation from verified textbook context.');
    const [aiPromptSaving, setAiPromptSaving] = useState(false);
    const [aiTimelineQuestionId, setAiTimelineQuestionId] = useState<number | null>(null);
    const [aiTimelineRows, setAiTimelineRows] = useState<any[]>([]);
    const [aiTimelineLoading, setAiTimelineLoading] = useState(false);
    // Tests management (Phase 5)
    const [adminTests, setAdminTests] = useState<any[]>([]);
    const [adminTestsLoading, setAdminTestsLoading] = useState(false);
    const [testQuestionSearch, setTestQuestionSearch] = useState('');
    const [testCandidateQuestions, setTestCandidateQuestions] = useState<any[]>([]);
    const [selectedTestQuestionIds, setSelectedTestQuestionIds] = useState<number[]>([]);
    const [testForm, setTestForm] = useState({
        title: '',
        description: '',
        test_type: 'mixed',
        time_limit_minutes: '30',
        negative_marking: true,
        negative_mark_value: '0.33',
    });
    const [testSaveLoading, setTestSaveLoading] = useState(false);
    // Textbook + chunk governance (Phase 4)
    const [adminBooks, setAdminBooks] = useState<any[]>([]);
    const [adminBooksLoading, setAdminBooksLoading] = useState(false);
    const [bookForm, setBookForm] = useState({ name: '', author: '', edition: '', subject: '', description: '' });
    const [chunks, setChunks] = useState<any[]>([]);
    const [chunksLoading, setChunksLoading] = useState(false);
    const [selectedChunkIds, setSelectedChunkIds] = useState<number[]>([]);
    const [chunkDiagnostics, setChunkDiagnostics] = useState<any | null>(null);
    const [chunkQuery, setChunkQuery] = useState('');
    const [chunkPageFilter, setChunkPageFilter] = useState('');
    const [referenceOverrides, setReferenceOverrides] = useState<any[]>([]);
    const [referenceMapForm, setReferenceMapForm] = useState({ question_id: '', textbook_id: '', chapter: '', page_number: '', excerpt: '' });
    const [referenceScreenshot, setReferenceScreenshot] = useState<File | null>(null);
    // Phase 7 analytics control
    const [weakAreaData, setWeakAreaData] = useState<any | null>(null);
    const [weakAreaLoading, setWeakAreaLoading] = useState(false);
    const [weakAreaUserId, setWeakAreaUserId] = useState('');
    // Phase 8 campaigns
    const [campaigns, setCampaigns] = useState<any[]>([]);
    const [campaignsLoading, setCampaignsLoading] = useState(false);
    const [campaignForm, setCampaignForm] = useState({ title: '', message: '', image_url: '', deep_link: '', role: 'all', active_only: true, scheduled_for: '' });
    const [campaignSaving, setCampaignSaving] = useState(false);
    // Phase 9 moderation queue
    const [issueQueue, setIssueQueue] = useState<any[]>([]);
    const [issueQueueLoading, setIssueQueueLoading] = useState(false);
    const [issueSort, setIssueSort] = useState<'most_reported' | 'most_attempted' | 'highest_impact'>('most_reported');
    const [issueStatusFilter, setIssueStatusFilter] = useState('');
    // Phase 10 revisions
    const [selectedRevisionQuestionId, setSelectedRevisionQuestionId] = useState('');
    const [revisionRows, setRevisionRows] = useState<any[]>([]);
    const [revisionDiff, setRevisionDiff] = useState<any[]>([]);
    const [revisionLoading, setRevisionLoading] = useState(false);
    // Audit explorer
    const [auditRows, setAuditRows] = useState<any[]>([]);
    const [auditLoading, setAuditLoading] = useState(false);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.replace('/login?next=/admin');
            return;
        }
        if (!authLoading && isAuthenticated && !hasAdminAccess) {
            router.replace('/dashboard');
            return;
        }
        if (isAuthenticated && hasAdminAccess) {
            Promise.all([
                analyticsAPI.getAdminDashboard().catch(() => ({ data: null })),
                analyticsAPI.getAnnouncements().catch(() => ({ data: [] })),
            ]).then(([dashRes, annRes]) => {
                setData(dashRes.data);
                setAnnouncements(Array.isArray(annRes.data) ? annRes.data : annRes.data?.results || []);
                setLoading(false);
            });
        }
    }, [isAuthenticated, authLoading, hasAdminAccess, router]);

    const handleCreateAnnouncement = async () => {
        if (!form.title.trim() || !form.message.trim()) return;
        setSubmitting(true);
        try {
            const payload: any = { title: form.title, message: form.message, priority: form.priority };
            if (form.expires_at) payload.expires_at = form.expires_at;
            const res = await analyticsAPI.createAnnouncement(payload);
            setAnnouncements([res.data, ...announcements]);
            setForm({ title: '', message: '', priority: 'normal', expires_at: '' });
            setShowForm(false);
        } catch { /* ignore */ }
        setSubmitting(false);
    };

    const handleDeleteAnnouncement = async (id: number) => {
        try {
            await analyticsAPI.deleteAnnouncement(id);
            setAnnouncements(announcements.filter(a => a.id !== id));
        } catch { /* ignore */ }
    };

    const fetchUsers = () => {
        setUsersLoading(true);
        const params: Record<string, string | number> = { limit: 300 };
        const effectiveSearch = userSearchTerm || adminSearch;
        if (effectiveSearch.trim()) params.q = effectiveSearch.trim();
        if (userRoleFilter !== 'all') params.role = userRoleFilter;
        if (userStatusFilter !== 'all') params.status = userStatusFilter;

        authAPI.adminListUsers(params)
            .then(res => setUserList(Array.isArray(res.data) ? res.data : res.data?.results || res.data?.users || []))
            .catch(() => {})
            .finally(() => setUsersLoading(false));
    };

    const fetchFeedback = () => {
        setFeedbackLoading(true);
        questionsAPI.getFeedback()
            .then(res => setFeedbackList(Array.isArray(res.data) ? res.data : res.data?.results || []))
            .catch(() => {})
            .finally(() => setFeedbackLoading(false));
    };

    const fetchQuestionSubjects = () => {
        Promise.all([
            questionsAPI.getSubjects().catch(() => ({ data: [] })),
            questionsAPI.getTopics().catch(() => ({ data: [] })),
        ])
            .then(([subjectRes, topicRes]) => {
                setQuestionSubjects(Array.isArray(subjectRes.data) ? subjectRes.data : subjectRes.data?.results || []);
                setQuestionTopics(Array.isArray(topicRes.data) ? topicRes.data : topicRes.data?.results || []);
            })
            .catch(() => {});
    };

    const fetchQuestions = (pageOverride?: number) => {
        setQuestionsLoading(true);
        const pageToLoad = pageOverride ?? questionPage;
        const params: Record<string, string | number> = { page: pageToLoad };
        const effectiveSearch = questionSearch.trim();
        if (effectiveSearch.trim()) params.search = effectiveSearch.trim();
        if (/^\d+$/.test(effectiveSearch)) params.question_id = Number(effectiveSearch);
        if (questionSubject) params.subject = Number(questionSubject);
        if (questionDifficulty) params.difficulty = questionDifficulty;
        if (questionYear) params.year = Number(questionYear);
        if (questionAccuracyMin) params.accuracy_min = Number(questionAccuracyMin);
        if (questionAccuracyMax) params.accuracy_max = Number(questionAccuracyMax);
        if (questionVerified === 'verified') params.is_verified_by_admin = 'true';
        if (questionVerified === 'unverified') params.is_verified_by_admin = 'false';
        if (questionFlagged === 'flagged') params.flagged = 'true';
        if (questionFlagged === 'clean') params.flagged = 'false';

        questionsAPI.list(params)
            .then((res) => {
                const payload = res.data;
                const rows = Array.isArray(payload) ? payload : payload?.results || [];
                setQuestionList(rows);
                setSelectedQuestionIds([]);
                setQuestionTotal(Number(payload?.count ?? rows.length));
                setQuestionHasNext(Boolean(payload?.next));
            })
            .catch(() => {
                setQuestionList([]);
                setQuestionTotal(0);
                setQuestionHasNext(false);
            })
            .finally(() => setQuestionsLoading(false));
    };

    const handleTabChange = (tab: AdminTabKey) => {
        setActiveTab(tab);
        if (tab === 'users' && userList.length === 0) fetchUsers();
        if (tab === 'feedback' && feedbackList.length === 0) fetchFeedback();
        if (tab === 'questions') {
            if (questionSubjects.length === 0) fetchQuestionSubjects();
            if (aiPromptVersions.length === 0) fetchAiPromptVersions();
            fetchQuestions(1);
            setQuestionPage(1);
        }
        if (tab === 'tests') {
            fetchAdminTests();
            fetchTestCandidateQuestions();
        }
        if (tab === 'textbooks') {
            fetchAdminBooks();
            fetchChunks();
            fetchChunkDiagnostics();
            fetchReferenceOverrides();
            if (questionSubjects.length === 0) fetchQuestionSubjects();
        }
        if (tab === 'analytics') {
            fetchWeakAreaControl();
        }
        if (tab === 'moderation') {
            fetchIssueQueue();
        }
        if (tab === 'broadcast') {
            fetchCampaigns();
        }
        if (tab === 'audit') {
            fetchAuditLogs();
        }
    };

    const fetchWeakAreaControl = async () => {
        setWeakAreaLoading(true);
        try {
            const params: Record<string, string | number> = {};
            if (weakAreaUserId) params.user_id = Number(weakAreaUserId);
            const res = await analyticsAPI.getWeakAreaControl(params);
            setWeakAreaData(res.data || null);
        } catch {
            setWeakAreaData(null);
        }
        setWeakAreaLoading(false);
    };

    const fetchIssueQueue = async () => {
        setIssueQueueLoading(true);
        try {
            const params: Record<string, string | number> = { sort: issueSort };
            if (issueStatusFilter) params.status = issueStatusFilter;
            const res = await questionsAPI.getAdminIssueQueue(params);
            const rows = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setIssueQueue(rows);
        } catch {
            setIssueQueue([]);
        }
        setIssueQueueLoading(false);
    };

    const handleIssueStatusUpdate = async (questionId: number, feedbackId: number, status: 'new' | 'in_progress' | 'resolved') => {
        const before = issueQueue;
        setIssueQueue((rows) => rows.map((row) => row.question_id === questionId ? { ...row, status } : row));
        try {
            await questionsAPI.updateFeedbackStatus(feedbackId, { status, notify_user: status === 'resolved' });
        } catch {
            // Optimistic rollback on failure.
            setIssueQueue(before);
        }
    };

    const fetchCampaigns = async () => {
        setCampaignsLoading(true);
        try {
            const res = await analyticsAPI.listCampaigns();
            const rows = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setCampaigns(rows);
        } catch {
            setCampaigns([]);
        }
        setCampaignsLoading(false);
    };

    const handleCreateCampaign = async () => {
        if (!campaignForm.title.trim() || !campaignForm.message.trim()) return;
        setCampaignSaving(true);
        try {
            await analyticsAPI.createCampaign({
                title: campaignForm.title,
                message: campaignForm.message,
                image_url: campaignForm.image_url,
                deep_link: campaignForm.deep_link,
                audience_filter: {
                    role: campaignForm.role === 'all' ? undefined : campaignForm.role,
                    active_only: campaignForm.active_only,
                },
                scheduled_for: campaignForm.scheduled_for || null,
                priority: 'normal',
                is_active: true,
            });
            setCampaignForm({ title: '', message: '', image_url: '', deep_link: '', role: 'all', active_only: true, scheduled_for: '' });
            fetchCampaigns();
        } catch {
            // Keep UI stable on API failure.
        }
        setCampaignSaving(false);
    };

    const handleSendCampaignNow = async (id: number) => {
        const before = campaigns;
        setCampaigns((rows) => rows.map((row) => row.id === id ? { ...row, delivery_status: 'sending' } : row));
        try {
            const res = await analyticsAPI.sendCampaignNow(id);
            const updated = res.data;
            setCampaigns((rows) => rows.map((row) => row.id === id ? updated : row));
        } catch {
            // Optimistic rollback on failure.
            setCampaigns(before);
        }
    };

    const fetchAuditLogs = async () => {
        setAuditLoading(true);
        try {
            const res = await authAPI.adminAuditLogs({ limit: 200 });
            const rows = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setAuditRows(rows);
        } catch {
            setAuditRows([]);
        }
        setAuditLoading(false);
    };

    const loadRevisionHistory = async () => {
        const id = Number(selectedRevisionQuestionId);
        if (!id) return;
        setRevisionLoading(true);
        try {
            const res = await questionsAPI.getRevisions(id);
            const rows = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setRevisionRows(rows);
            setRevisionDiff([]);
        } catch {
            setRevisionRows([]);
            setRevisionDiff([]);
        }
        setRevisionLoading(false);
    };

    const loadRevisionDiff = async (questionId: number, revisionId?: number) => {
        setRevisionLoading(true);
        try {
            const res = await questionsAPI.getRevisionDiff(questionId, revisionId);
            const rows = res.data?.changed_fields || [];
            setRevisionDiff(rows);
        } catch {
            setRevisionDiff([]);
        }
        setRevisionLoading(false);
    };

    const handleUndoRevision = async (questionId: number, revisionId?: number) => {
        try {
            await questionsAPI.undoRevision(questionId, revisionId);
            await loadRevisionHistory();
            await fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const fetchAiPromptVersions = async () => {
        try {
            const res = await questionsAPI.aiPromptVersions();
            const rows = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setAiPromptVersions(rows);
        } catch {
            setAiPromptVersions([]);
        }
    };

    const handleCreateAiPromptVersion = async () => {
        if (!aiPromptName.trim() || !aiPromptText.trim()) return;
        setAiPromptSaving(true);
        try {
            await questionsAPI.createAiPromptVersion({
                name: aiPromptName.trim(),
                prompt_text: aiPromptText.trim(),
                activate: true,
            });
            await fetchAiPromptVersions();
        } catch {
            // Keep UI stable on API failure.
        }
        setAiPromptSaving(false);
    };

    const handleActivatePromptVersion = async (versionId: number) => {
        try {
            await questionsAPI.activateAiPromptVersion(versionId);
            await fetchAiPromptVersions();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const handleLoadAiTimeline = async (questionId: number) => {
        setAiTimelineLoading(true);
        setAiTimelineQuestionId(questionId);
        try {
            const res = await questionsAPI.aiTimeline(questionId);
            const rows = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setAiTimelineRows(rows);
        } catch {
            setAiTimelineRows([]);
        }
        setAiTimelineLoading(false);
    };

    const fetchAdminTests = async () => {
        setAdminTestsLoading(true);
        try {
            const res = await testsAPI.list();
            const rows = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setAdminTests(rows);
        } catch {
            setAdminTests([]);
        }
        setAdminTestsLoading(false);
    };

    const fetchTestCandidateQuestions = async () => {
        try {
            const params: Record<string, string | number> = { page: 1 };
            if (testQuestionSearch.trim()) params.search = testQuestionSearch.trim();
            const res = await questionsAPI.list(params);
            const rows = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setTestCandidateQuestions(rows);
        } catch {
            setTestCandidateQuestions([]);
        }
    };

    const handleCreateManualTest = async () => {
        if (!testForm.title.trim()) return;
        setTestSaveLoading(true);
        try {
            await testsAPI.createManual({
                title: testForm.title,
                description: testForm.description,
                test_type: testForm.test_type,
                question_ids: selectedTestQuestionIds,
                time_limit_minutes: Number(testForm.time_limit_minutes || 30),
                negative_marking: testForm.negative_marking,
                negative_mark_value: Number(testForm.negative_mark_value || 0.33),
            });
            setTestForm({
                title: '',
                description: '',
                test_type: 'mixed',
                time_limit_minutes: '30',
                negative_marking: true,
                negative_mark_value: '0.33',
            });
            setSelectedTestQuestionIds([]);
            fetchAdminTests();
        } catch {
            // Keep UI stable on API failure.
        }
        setTestSaveLoading(false);
    };

    const toggleTestQuestionSelection = (id: number) => {
        setSelectedTestQuestionIds((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]));
    };

    const runTestAction = async (action: 'publish' | 'unpublish' | 'duplicate', id: number) => {
        try {
            if (action === 'publish') await testsAPI.publish(id);
            if (action === 'unpublish') await testsAPI.unpublish(id);
            if (action === 'duplicate') await testsAPI.duplicate(id);
            fetchAdminTests();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const fetchAdminBooks = async () => {
        setAdminBooksLoading(true);
        try {
            const res = await textbooksAPI.list();
            const rows = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setAdminBooks(rows);
        } catch {
            setAdminBooks([]);
        }
        setAdminBooksLoading(false);
    };

    const handleCreateBook = async () => {
        if (!bookForm.name.trim() || !bookForm.author.trim() || !bookForm.subject) return;
        try {
            await textbooksAPI.create({
                name: bookForm.name,
                author: bookForm.author,
                edition: bookForm.edition,
                subject: Number(bookForm.subject),
                description: bookForm.description,
            });
            setBookForm({ name: '', author: '', edition: '', subject: '', description: '' });
            fetchAdminBooks();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const fetchChunks = async () => {
        setChunksLoading(true);
        try {
            const params: Record<string, string | number> = {};
            if (chunkQuery.trim()) params.q = chunkQuery.trim();
            if (chunkPageFilter.trim()) params.page_number = Number(chunkPageFilter);
            const res = await textbooksAPI.getChunks(params);
            const rows = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setChunks(rows);
        } catch {
            setChunks([]);
        }
        setChunksLoading(false);
    };

    const fetchChunkDiagnostics = async () => {
        try {
            const res = await textbooksAPI.getChunkDiagnostics();
            setChunkDiagnostics(res.data || null);
        } catch {
            setChunkDiagnostics(null);
        }
    };

    const toggleChunkSelection = (chunkId: number) => {
        setSelectedChunkIds((prev) => (prev.includes(chunkId) ? prev.filter((v) => v !== chunkId) : [...prev, chunkId]));
    };

    const runChunkAction = async (action: 'delete' | 'merge' | 'rechunk', chunkId?: number) => {
        try {
            if (action === 'delete' && chunkId) await textbooksAPI.deleteChunk(chunkId);
            if (action === 'merge') await textbooksAPI.mergeChunks(selectedChunkIds);
            if (action === 'rechunk') await textbooksAPI.rechunk(selectedChunkIds);
            setSelectedChunkIds([]);
            fetchChunks();
            fetchChunkDiagnostics();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const handleChunkMark = async (chunkId: number, status: 'approved' | 'rejected' | 'pending') => {
        try {
            await textbooksAPI.markChunk(chunkId, status);
            fetchChunks();
            fetchChunkDiagnostics();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const fetchReferenceOverrides = async () => {
        try {
            const res = await textbooksAPI.getReferenceOverrides({ limit: 50 });
            const rows = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setReferenceOverrides(rows);
        } catch {
            setReferenceOverrides([]);
        }
    };

    const handleSaveReferenceMap = async () => {
        if (!referenceMapForm.question_id || !referenceMapForm.page_number) return;
        try {
            const formData = new FormData();
            formData.append('question_id', referenceMapForm.question_id);
            if (referenceMapForm.textbook_id) formData.append('textbook_id', referenceMapForm.textbook_id);
            formData.append('chapter', referenceMapForm.chapter);
            formData.append('page_number', referenceMapForm.page_number);
            formData.append('excerpt', referenceMapForm.excerpt);
            if (referenceScreenshot) formData.append('screenshot', referenceScreenshot);
            await textbooksAPI.mapQuestionReference(formData);
            setReferenceMapForm({ question_id: '', textbook_id: '', chapter: '', page_number: '', excerpt: '' });
            setReferenceScreenshot(null);
            fetchReferenceOverrides();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const moduleTabs: { key: AdminTabKey; label: string; icon: any }[] = [
        { key: 'overview', label: 'Overview', icon: TrendingUp },
        { key: 'questions', label: 'Question Bank', icon: BookOpen },
        { key: 'users', label: 'Users & Tokens', icon: Users },
        { key: 'feedback', label: 'Feedback Queue', icon: MessageSquare },
        { key: 'tests', label: 'Tests Engine', icon: FileText },
        { key: 'textbooks', label: 'Textbooks', icon: Database },
        { key: 'analytics', label: 'Analytics', icon: BarChart3 },
        { key: 'moderation', label: 'Moderation', icon: ShieldCheck },
        { key: 'broadcast', label: 'Broadcast', icon: Megaphone },
        { key: 'security', label: 'Security', icon: Shield },
        { key: 'audit', label: 'Audit Logs', icon: FileSearch },
        { key: 'finance', label: 'Finance', icon: Wallet },
        { key: 'ai', label: 'AI Ops', icon: Sparkles },
    ];

    const handleGrantTokens = async () => {
        if (!grantUserId || !grantAmount) return;
        setGranting(true);
        setGrantMsg('');
        try {
            const res = await authAPI.adminGrantTokens({
                user_id: Number(grantUserId),
                amount: Number(grantAmount),
                note: grantNote || undefined,
            });
            setGrantMsg(res.data?.message || 'Tokens granted!');
            setGrantAmount('');
            setGrantNote('');
            fetchUsers();
        } catch (err: any) {
            setGrantMsg(err?.response?.data?.error || 'Failed to grant tokens');
        }
        setGranting(false);
    };

    const handleResolveFeedback = async (id: number) => {
        try {
            await questionsAPI.resolveFeedback(id);
            setFeedbackList(feedbackList.map(f => f.id === id ? { ...f, is_resolved: true } : f));
        } catch { /* ignore */ }
    };

    const handleApplyUserFilters = () => {
        fetchUsers();
    };

    const handleResetUserFilters = () => {
        setUserSearchTerm('');
        setUserRoleFilter('all');
        setUserStatusFilter('all');
        setTimeout(() => fetchUsers(), 0);
    };

    const handleToggleUserBlock = async (targetUserId: number, currentlyActive: boolean) => {
        setUserActionLoadingId(targetUserId);
        setUserActionMessage('');
        try {
            const blocked = currentlyActive;
            await authAPI.adminToggleUserBlock(targetUserId, blocked);
            setUserActionMessage(blocked ? 'User blocked successfully' : 'User unblocked successfully');
            fetchUsers();
        } catch {
            setUserActionMessage('Could not update user status.');
        }
        setUserActionLoadingId(null);
    };

    const handleToggleUserRole = async (targetUserId: number, currentRole: string) => {
        setUserActionLoadingId(targetUserId);
        setUserActionMessage('');
        try {
            const nextRole = currentRole === 'admin' ? 'student' : 'admin';
            await authAPI.adminUpdateUserRole(targetUserId, nextRole);
            setUserActionMessage(`Role updated to ${nextRole}`);
            fetchUsers();
        } catch {
            setUserActionMessage('Could not update user role.');
        }
        setUserActionLoadingId(null);
    };

    const handleResetUserProgress = async (targetUserId: number) => {
        setUserActionLoadingId(targetUserId);
        setUserActionMessage('');
        try {
            await authAPI.adminResetUserProgress(targetUserId);
            setUserActionMessage('User progress reset complete');
            fetchUsers();
        } catch {
            setUserActionMessage('Could not reset user progress.');
        }
        setUserActionLoadingId(null);
    };

    const runSystemAction = async (action: 'resetAttempts' | 'clearAnalytics' | 'rerunEvaluation') => {
        const payload: { scope: 'all' | 'user'; user_id?: number } = { scope: systemScope };
        if (systemScope === 'user') {
            const id = Number(systemUserId);
            if (!id) return;
            payload.user_id = id;
        }

        setSystemActionLoading(true);
        setUserActionMessage('');
        try {
            if (action === 'resetAttempts') await authAPI.adminResetAttempts(payload);
            if (action === 'clearAnalytics') await authAPI.adminClearAnalytics(payload);
            if (action === 'rerunEvaluation') await authAPI.adminRerunEvaluation(payload);
            setUserActionMessage('System action completed');
            fetchUsers();
        } catch {
            setUserActionMessage('System action failed.');
        }
        setSystemActionLoading(false);
    };

    const handleQuestionFilterApply = () => {
        setQuestionPage(1);
        fetchQuestions(1);
    };

    const handleQuestionSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key !== 'Enter') return;
        e.preventDefault();
        handleQuestionFilterApply();
    };

    const normalizeQuestionText = (text: string) =>
        String(text || '')
            .toLowerCase()
            .replace(/\s+/g, ' ')
            .replace(/[\*`#]/g, '')
            .trim();

    const duplicateQuestionInfo = useMemo(() => {
        const counts: Record<string, number> = {};
        for (const q of questionList) {
            const key = normalizeQuestionText(q?.question_text || '');
            if (!key) continue;
            counts[key] = (counts[key] || 0) + 1;
        }
        return counts;
    }, [questionList]);

    const toggleQuestionExpanded = (id: number) => {
        setExpandedQuestionIds((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]));
    };

    const selectDuplicateQuestionsOnPage = () => {
        const grouped: Record<string, number[]> = {};
        for (const q of questionList) {
            const key = normalizeQuestionText(q?.question_text || '');
            if (!key) continue;
            if (!grouped[key]) grouped[key] = [];
            grouped[key].push(Number(q.id));
        }

        const duplicateIdsToSelect: number[] = [];
        for (const ids of Object.values(grouped)) {
            if (ids.length <= 1) continue;
            const sorted = [...ids].sort((a, b) => a - b);
            duplicateIdsToSelect.push(...sorted.slice(1));
        }

        setSelectedQuestionIds(duplicateIdsToSelect);
    };

    const handleQuestionFilterReset = () => {
        setQuestionSearch('');
        setQuestionSubject('');
        setQuestionDifficulty('');
        setQuestionYear('');
        setQuestionAccuracyMin('');
        setQuestionAccuracyMax('');
        setQuestionVerified('all');
        setQuestionFlagged('all');
        setExpandedQuestionIds([]);
        setQuestionPage(1);
        fetchQuestions(1);
    };

    const handleQuestionVerifyToggle = async (id: number, currentlyVerified: boolean) => {
        try {
            if (currentlyVerified) {
                await questionsAPI.unverify(id);
            } else {
                await questionsAPI.verify(id, 'Verified in admin control tower');
            }
            fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const toggleQuestionSelection = (id: number) => {
        setSelectedQuestionIds((prev) => prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]);
    };

    const toggleSelectAllVisibleQuestions = () => {
        const currentIds = questionList.map((q: any) => Number(q.id));
        const isAllSelected = currentIds.every((id: number) => selectedQuestionIds.includes(id));
        if (isAllSelected) {
            setSelectedQuestionIds((prev) => prev.filter((id) => !currentIds.includes(id)));
            return;
        }
        setSelectedQuestionIds((prev) => Array.from(new Set([...prev, ...currentIds])));
    };

    const runBulkVerifyAction = async (verify: boolean) => {
        if (selectedQuestionIds.length === 0) return;
        setBulkActionLoading(true);
        try {
            await Promise.all(
                selectedQuestionIds.map((id) => verify ? questionsAPI.verify(id, 'Bulk verified in admin control tower') : questionsAPI.unverify(id))
            );
            fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
        setBulkActionLoading(false);
    };

    const runBulkFormatFixAction = async () => {
        if (selectedQuestionIds.length === 0) return;
        setBulkActionLoading(true);
        try {
            await Promise.all(selectedQuestionIds.map((id) => questionsAPI.formatFix(id)));
            fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
        setBulkActionLoading(false);
    };

    const startInlineEdit = (q: any) => {
        const relatedIds = Array.isArray(q.related_question_ids) ? q.related_question_ids.join(', ') : '';
        setEditingQuestionId(Number(q.id));
        setEditingForm({
            question_text: q.question_text || '',
            option_a: q.option_a || '',
            option_b: q.option_b || '',
            option_c: q.option_c || '',
            option_d: q.option_d || '',
            correct_answer: q.correct_answer || '',
            explanation: q.explanation || '',
            difficulty: q.difficulty || 'medium',
            year: String(q.year || ''),
            subject: String(q.subject || ''),
            topic: String(q.topic || ''),
            paper: String(q.paper || ''),
            concept_id: q.concept_id || '',
            book_name: q.book_name || '',
            chapter: q.chapter || '',
            page_number: q.page_number || '',
            reference_text: q.reference_text || '',
            related_question_ids: relatedIds,
        });
    };

    const cancelInlineEdit = () => {
        setEditingQuestionId(null);
        setEditingForm({
            question_text: '',
            option_a: '',
            option_b: '',
            option_c: '',
            option_d: '',
            correct_answer: '',
            explanation: '',
            difficulty: 'medium',
            year: '',
            subject: '',
            topic: '',
            paper: '',
            concept_id: '',
            book_name: '',
            chapter: '',
            page_number: '',
            reference_text: '',
            related_question_ids: '',
        });
    };

    const parseRelatedIds = (value: string) => {
        return value
            .split(',')
            .map((item) => Number(item.trim()))
            .filter((id) => Number.isInteger(id) && id > 0);
    };

    const saveInlineEdit = async (id: number) => {
        setSavingEdit(true);
        try {
            await questionsAPI.update(id, {
                question_text: editingForm.question_text,
                option_a: editingForm.option_a,
                option_b: editingForm.option_b,
                option_c: editingForm.option_c,
                option_d: editingForm.option_d,
                correct_answer: editingForm.correct_answer,
                explanation: editingForm.explanation,
                difficulty: editingForm.difficulty,
                year: Number(editingForm.year),
                subject: Number(editingForm.subject),
                topic: editingForm.topic ? Number(editingForm.topic) : null,
                paper: editingForm.paper ? Number(editingForm.paper) : 0,
                concept_id: editingForm.concept_id,
                book_name: editingForm.book_name,
                chapter: editingForm.chapter,
                page_number: editingForm.page_number,
                reference_text: editingForm.reference_text,
            });
            const relatedIds = parseRelatedIds(editingForm.related_question_ids);
            await questionsAPI.linkRelatedPyqs(id, relatedIds);
            cancelInlineEdit();
            fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
        setSavingEdit(false);
    };

    const handleCreateQuestion = async () => {
        if (!createForm.question_text.trim() || !createForm.subject || !createForm.year) return;
        setCreateLoading(true);
        try {
            const payload: Record<string, unknown> = {
                question_text: createForm.question_text,
                option_a: createForm.option_a,
                option_b: createForm.option_b,
                option_c: createForm.option_c,
                option_d: createForm.option_d,
                correct_answer: createForm.correct_answer,
                year: Number(createForm.year),
                subject: Number(createForm.subject),
                difficulty: createForm.difficulty,
                explanation: createForm.explanation,
                paper: createForm.paper ? Number(createForm.paper) : 0,
                concept_id: createForm.concept_id,
                book_name: createForm.book_name,
                chapter: createForm.chapter,
                page_number: createForm.page_number,
                reference_text: createForm.reference_text,
            };
            if (createForm.topic) payload.topic = Number(createForm.topic);
            const createRes = await questionsAPI.create(payload);
            const createdId = createRes?.data?.id;
            const relatedIds = parseRelatedIds(createForm.related_question_ids);
            if (createdId && relatedIds.length > 0) {
                await questionsAPI.linkRelatedPyqs(Number(createdId), relatedIds);
            }
            setCreateForm({
                question_text: '',
                option_a: '',
                option_b: '',
                option_c: '',
                option_d: '',
                correct_answer: 'A',
                year: '',
                subject: '',
                topic: '',
                paper: '',
                difficulty: 'medium',
                explanation: '',
                concept_id: '',
                book_name: '',
                chapter: '',
                page_number: '',
                reference_text: '',
                related_question_ids: '',
            });
            setQuestionPage(1);
            fetchQuestions(1);
        } catch {
            // Keep UI stable on API failure.
        }
        setCreateLoading(false);
    };

    const handleDuplicateQuestion = async (id: number) => {
        const shouldDuplicate = window.confirm('Create a duplicate of this question? This adds a new question with a different ID.');
        if (!shouldDuplicate) return;
        try {
            await questionsAPI.duplicate(id);
            fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const handleArchiveQuestion = async (id: number) => {
        try {
            await questionsAPI.archive(id);
            fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const handleDeleteQuestion = async (id: number) => {
        try {
            await questionsAPI.remove(id);
            fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const handleFormatFix = async (id: number) => {
        try {
            await questionsAPI.formatFix(id);
            fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const handleForceRegenerate = async (id: number) => {
        try {
            await questionsAPI.forceRegenerate(id);
            fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const handleToggleAiLock = async (id: number, lockAnswer: boolean, lockExplanation: boolean) => {
        try {
            await questionsAPI.aiLock(id, { lock_answer: lockAnswer, lock_explanation: lockExplanation });
            fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const handleAiOverridePrompt = async (id: number) => {
        const answer = window.prompt('Admin answer override (leave blank to skip):', '');
        const explanation = window.prompt('Admin explanation override (leave blank to skip):', '');
        const mnemonic = window.prompt('Admin mnemonic override (leave blank to skip):', '');
        const payload: Record<string, unknown> = {};
        if (answer !== null && answer !== '') payload.admin_answer_override = answer;
        if (explanation !== null && explanation !== '') payload.admin_explanation_override = explanation;
        if (mnemonic !== null && mnemonic !== '') payload.admin_mnemonic_override = mnemonic;
        if (Object.keys(payload).length === 0) return;

        try {
            await questionsAPI.aiOverride(id, payload);
            fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const handleImportPreview = async () => {
        if (!importPayload.trim()) return;
        setImportPreviewLoading(true);
        try {
            if (importFormat === 'json') {
                const parsed = JSON.parse(importPayload);
                const rows = Array.isArray(parsed) ? parsed : [parsed];
                const res = await questionsAPI.importPreview({ format: 'json', rows });
                setImportPreviewResult(res.data);
            } else {
                const res = await questionsAPI.importPreview({ format: 'csv', csv_text: importPayload });
                setImportPreviewResult(res.data);
            }
        } catch (error: any) {
            setImportPreviewResult({
                format: importFormat,
                total_rows: 0,
                valid_rows: 0,
                invalid_rows: 1,
                to_create: 0,
                to_update: 0,
                errors: [{ row: 0, errors: error?.message || 'Invalid import payload' }],
            });
        }
        setImportPreviewLoading(false);
    };

    const handleBulkMetadataUpdate = async () => {
        if (selectedQuestionIds.length === 0) return;
        const payload: Record<string, unknown> = { ids: selectedQuestionIds };
        if (bulkMetaSubject) payload.subject = Number(bulkMetaSubject);
        if (bulkMetaTopic) payload.topic = Number(bulkMetaTopic);
        if (bulkMetaDifficulty) payload.difficulty = bulkMetaDifficulty;
        if (bulkMetaYear) payload.year = Number(bulkMetaYear);
        if (bulkMetaPaper) payload.paper = Number(bulkMetaPaper);
        if (Object.keys(payload).length <= 1) return;

        setBulkMetaLoading(true);
        try {
            await questionsAPI.bulkMetadataUpdate(payload);
            fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
        setBulkMetaLoading(false);
    };

    const handleBulkDelete = async () => {
        if (selectedQuestionIds.length === 0 || bulkDeleteConfirm !== 'DELETE') return;
        setBulkDeleteLoading(true);
        try {
            await questionsAPI.bulkDelete({ ids: selectedQuestionIds, confirm: 'DELETE' });
            setBulkDeleteConfirm('');
            fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
        setBulkDeleteLoading(false);
    };

    const fetchExtractionJobs = async () => {
        setExtractionJobsLoading(true);
        try {
            const res = await questionsAPI.extractionJobs({ limit: 20 });
            const rows = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setExtractionJobs(rows);
        } catch {
            setExtractionJobs([]);
        }
        setExtractionJobsLoading(false);
    };

    const handleExtractionUpload = async () => {
        if (!extractionFile) return;
        setExtractionLoading(true);
        try {
            const formData = new FormData();
            formData.append('file', extractionFile);
            await questionsAPI.extractionUpload(formData);
            setExtractionFile(null);
            fetchExtractionJobs();
        } catch {
            // Keep UI stable on API failure.
        }
        setExtractionLoading(false);
    };

    const handleExtractionRetry = async (jobId: number) => {
        try {
            await questionsAPI.extractionRetry(jobId);
            fetchExtractionJobs();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const fetchExtractionItems = async (jobId: number) => {
        setExtractionItemsLoading(true);
        try {
            const res = await questionsAPI.extractionItems(jobId);
            const rows = Array.isArray(res.data) ? res.data : res.data?.results || [];
            setExtractionItems(rows);
            setSelectedExtractionJobId(jobId);
        } catch {
            setExtractionItems([]);
        }
        setExtractionItemsLoading(false);
    };

    const beginExtractionItemEdit = (item: any) => {
        setEditingExtractionItemId(Number(item.id));
        setEditingExtractionItem({ ...item });
    };

    const cancelExtractionItemEdit = () => {
        setEditingExtractionItemId(null);
        setEditingExtractionItem(null);
    };

    const saveExtractionItemEdit = async (itemId: number) => {
        if (!editingExtractionItem) return;
        try {
            await questionsAPI.extractionItemUpdate(itemId, {
                question_text: editingExtractionItem.question_text,
                option_a: editingExtractionItem.option_a,
                option_b: editingExtractionItem.option_b,
                option_c: editingExtractionItem.option_c,
                option_d: editingExtractionItem.option_d,
                correct_answer: editingExtractionItem.correct_answer,
                explanation: editingExtractionItem.explanation,
                year: editingExtractionItem.year,
                paper: editingExtractionItem.paper,
                subject: editingExtractionItem.subject,
                topic: editingExtractionItem.topic,
                review_note: editingExtractionItem.review_note,
            });
            cancelExtractionItemEdit();
            if (selectedExtractionJobId) fetchExtractionItems(selectedExtractionJobId);
        } catch {
            // Keep UI stable on API failure.
        }
    };

    const runExtractionItemAction = async (action: 'autotag' | 'approve' | 'reject' | 'publish', itemId: number) => {
        try {
            if (action === 'autotag') await questionsAPI.extractionItemAutotag(itemId);
            if (action === 'approve') await questionsAPI.extractionItemApprove(itemId);
            if (action === 'reject') await questionsAPI.extractionItemReject(itemId, { review_note: 'Rejected during admin review' });
            if (action === 'publish') await questionsAPI.extractionItemPublish(itemId);
            if (selectedExtractionJobId) fetchExtractionItems(selectedExtractionJobId);
            if (action === 'publish') fetchQuestions();
        } catch {
            // Keep UI stable on API failure.
        }
    };

    if (authLoading || loading) {
        return (
            <div className="min-h-screen bg-background flex">
                <Sidebar />
                <div className="flex-1 flex flex-col">
                    <Header />
                    <main className="flex-1 p-6 flex items-center justify-center">
                        <div className="animate-pulse text-muted-foreground">Loading admin dashboard...</div>
                    </main>
                </div>
            </div>
        );
    }

    const stats = [
        { label: 'Total Users', value: data?.total_users || 0, icon: Users, color: 'text-blue-500' },
        { label: 'Active Today', value: data?.active_today || 0, icon: TrendingUp, color: 'text-green-500' },
        { label: 'Total Questions', value: data?.total_questions || 0, icon: BookOpen, color: 'text-purple-500' },
        { label: 'Tests Taken', value: data?.total_tests_taken || 0, icon: FileText, color: 'text-cyan-500' },
        { label: 'With Answers', value: `${data?.answer_percentage?.toFixed(1) || 0}%`, icon: CheckCircle, color: 'text-emerald-500' },
        { label: 'With Explanations', value: data?.questions_with_explanation || 0, icon: CheckCircle, color: 'text-teal-500' },
        { label: 'Unresolved Feedback', value: data?.unresolved_feedback || 0, icon: AlertTriangle, color: data?.unresolved_feedback ? 'text-amber-500' : 'text-slate-400' },
    ];

    return (
        <div className="min-h-screen bg-background flex">
            <Sidebar />
            <div className="flex-1 flex flex-col">
                <Header />
                <main className="flex-1 p-6 page-container space-y-6">
                    {/* Title */}
                    <div className="flex items-center gap-3">
                        <Shield className="w-7 h-7 text-primary" />
                        <div>
                            <h1 className="text-2xl font-bold">Admin Dashboard</h1>
                            <p className="text-sm text-muted-foreground">Platform overview & management</p>
                        </div>
                    </div>

                    {/* Tabs */}
                    <div className="rounded-xl border bg-card p-3">
                        <div className="flex flex-wrap gap-1.5">
                        {moduleTabs.map(tab => (
                            <button key={tab.key}
                                onClick={() => handleTabChange(tab.key)}
                                className={`flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${activeTab === tab.key ? 'bg-primary text-primary-foreground shadow-sm' : 'bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted'}`}>
                                <tab.icon className="w-4 h-4" /> {tab.label}
                            </button>
                        ))}
                        </div>
                    </div>

                    <div className="rounded-xl border bg-card p-3 flex flex-wrap items-end gap-3">
                        <div className="min-w-56 flex-1">
                            <label className="text-xs font-medium text-muted-foreground block mb-1">Global Admin Search</label>
                            <Input
                                placeholder="Search users, questions, IDs, announcements..."
                                value={adminSearch}
                                onChange={(e) => setAdminSearch(e.target.value)}
                            />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-muted-foreground block mb-1">Quick Filter</label>
                            <select
                                className="h-10 rounded-md border bg-background px-3 text-sm"
                                value={adminFilter}
                                onChange={(e) => setAdminFilter(e.target.value)}
                            >
                                <option value="all">All</option>
                                <option value="priority">Priority</option>
                                <option value="pending">Pending</option>
                                <option value="flagged">Flagged</option>
                                <option value="verified">Verified</option>
                            </select>
                        </div>
                        <Button variant="outline" onClick={() => { setAdminSearch(''); setAdminFilter('all'); }}>
                            Reset
                        </Button>
                    </div>

                    {/* ===== OVERVIEW TAB ===== */}
                    {activeTab === 'overview' && (<>

                    <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-3">
                        <Card>
                            <CardContent className="p-4">
                                <p className="text-xs text-muted-foreground">Modules Mapped</p>
                                <p className="text-2xl font-bold">{moduleTabs.length}</p>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardContent className="p-4">
                                <p className="text-xs text-muted-foreground">Search Scope</p>
                                <p className="text-sm font-medium truncate">{adminSearch || 'Global control scope'}</p>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardContent className="p-4">
                                <p className="text-xs text-muted-foreground">Current Filter</p>
                                <p className="text-sm font-medium capitalize">{adminFilter}</p>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardContent className="p-4">
                                <p className="text-xs text-muted-foreground">Pending Feedback</p>
                                <p className="text-2xl font-bold">{data?.unresolved_feedback || 0}</p>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Stats Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                        {stats.map(s => (
                            <Card key={s.label}>
                                <CardContent className="p-4 flex items-center gap-3">
                                    <s.icon className={`w-8 h-8 ${s.color} shrink-0`} />
                                    <div>
                                        <p className="text-2xl font-bold">{s.value}</p>
                                        <p className="text-xs text-muted-foreground">{s.label}</p>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>

                    {/* Question Quality */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-lg">
                                <BookOpen className="w-5 h-5" /> Question Quality
                            </CardTitle>
                            <CardDescription>Answer and explanation coverage</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-3">
                                <div>
                                    <div className="flex justify-between text-sm mb-1">
                                        <span>Questions with correct answers</span>
                                        <span className="font-medium">{data?.questions_with_answer}/{data?.total_questions}</span>
                                    </div>
                                    <div className="w-full bg-muted rounded-full h-2.5">
                                        <div
                                            className="bg-emerald-500 h-2.5 rounded-full transition-all"
                                            style={{ width: `${data?.answer_percentage || 0}%` }}
                                        />
                                    </div>
                                </div>
                                <div>
                                    <div className="flex justify-between text-sm mb-1">
                                        <span>Questions with explanations</span>
                                        <span className="font-medium">{data?.questions_with_explanation}/{data?.total_questions}</span>
                                    </div>
                                    <div className="w-full bg-muted rounded-full h-2.5">
                                        <div
                                            className="bg-teal-500 h-2.5 rounded-full transition-all"
                                            style={{ width: `${data?.total_questions ? (data.questions_with_explanation / data.total_questions * 100) : 0}%` }}
                                        />
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <div className="grid lg:grid-cols-2 gap-6">
                        {/* Announcements */}
                        <Card>
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <CardTitle className="flex items-center gap-2 text-lg">
                                        <Megaphone className="w-5 h-5" /> Announcements
                                    </CardTitle>
                                    <Button size="sm" variant={showForm ? 'outline' : 'default'} onClick={() => setShowForm(!showForm)}>
                                        <Plus className="w-4 h-4 mr-1" /> {showForm ? 'Cancel' : 'New'}
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                {showForm && (
                                    <div className="space-y-2 p-3 rounded-lg border bg-muted/50">
                                        <Input placeholder="Title" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} />
                                        <textarea
                                            className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-20 resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                                            placeholder="Message..."
                                            value={form.message}
                                            onChange={e => setForm({ ...form, message: e.target.value })}
                                        />
                                        <div className="flex gap-2">
                                            <select
                                                className="rounded-md border bg-background px-3 py-2 text-sm"
                                                value={form.priority}
                                                onChange={e => setForm({ ...form, priority: e.target.value })}
                                            >
                                                <option value="low">Low</option>
                                                <option value="normal">Normal</option>
                                                <option value="high">High</option>
                                                <option value="urgent">Urgent</option>
                                            </select>
                                            <Input type="datetime-local" value={form.expires_at} onChange={e => setForm({ ...form, expires_at: e.target.value })} placeholder="Expires (optional)" />
                                            <Button size="sm" onClick={handleCreateAnnouncement} disabled={submitting}>
                                                {submitting ? 'Posting...' : 'Post'}
                                            </Button>
                                        </div>
                                    </div>
                                )}
                                {announcements.length === 0 && <p className="text-sm text-muted-foreground text-center py-4">No announcements yet</p>}
                                {announcements.map(a => (
                                    <div key={a.id} className="flex items-start gap-3 p-3 rounded-lg border">
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className="font-medium text-sm truncate">{a.title}</span>
                                                <Badge className={`text-[10px] px-1.5 ${priorityColors[a.priority] || ''}`}>{a.priority}</Badge>
                                                {a.is_expired && <Badge variant="outline" className="text-[10px]">Expired</Badge>}
                                            </div>
                                            <p className="text-xs text-muted-foreground line-clamp-2">{a.message}</p>
                                        </div>
                                        <Button variant="ghost" size="icon" className="shrink-0 h-8 w-8 text-destructive" onClick={() => handleDeleteAnnouncement(a.id)}>
                                            <Trash2 className="w-4 h-4" />
                                        </Button>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>

                        {/* Recent Signups */}
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2 text-lg">
                                    <Users className="w-5 h-5" /> Recent Signups
                                </CardTitle>
                                <CardDescription>Last 10 registered users</CardDescription>
                            </CardHeader>
                            <CardContent>
                                {(!data?.recent_signups || data.recent_signups.length === 0) ? (
                                    <p className="text-sm text-muted-foreground text-center py-4">No recent signups</p>
                                ) : (
                                    <div className="space-y-2">
                                        {data.recent_signups.map(u => (
                                            <div key={u.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-muted/50">
                                                <div className="flex items-center gap-3">
                                                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-semibold text-primary">
                                                        {u.username.charAt(0).toUpperCase()}
                                                    </div>
                                                    <span className="text-sm font-medium">{u.username}</span>
                                                </div>
                                                <span className="text-xs text-muted-foreground">
                                                    <Clock className="w-3 h-3 inline mr-1" />
                                                    {new Date(u.date_joined).toLocaleDateString()}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>

                    </>)}

                    {/* ===== USERS & TOKENS TAB ===== */}
                    {activeTab === 'users' && (
                        <div className="space-y-6">
                            {/* Grant Tokens */}
                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2 text-lg">
                                        <Gift className="w-5 h-5" /> Grant Tokens
                                    </CardTitle>
                                    <CardDescription>Give tokens to any user</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="flex flex-wrap gap-3 items-end">
                                        <div>
                                            <label className="text-xs font-medium text-muted-foreground block mb-1">User ID</label>
                                            <Input className="w-24" type="number" placeholder="ID"
                                                value={grantUserId} onChange={e => setGrantUserId(e.target.value)} />
                                        </div>
                                        <div>
                                            <label className="text-xs font-medium text-muted-foreground block mb-1">Tokens</label>
                                            <Input className="w-24" type="number" placeholder="Amount"
                                                value={grantAmount} onChange={e => setGrantAmount(e.target.value)} />
                                        </div>
                                        <div className="flex-1 min-w-50">
                                            <label className="text-xs font-medium text-muted-foreground block mb-1">Note (optional)</label>
                                            <Input placeholder="Reason for granting tokens"
                                                value={grantNote} onChange={e => setGrantNote(e.target.value)} />
                                        </div>
                                        <Button onClick={handleGrantTokens} disabled={granting || !grantUserId || !grantAmount}>
                                            <Zap className="w-4 h-4 mr-1" /> {granting ? 'Granting...' : 'Grant'}
                                        </Button>
                                    </div>
                                    {grantMsg && <p className="text-sm mt-2 text-primary font-medium">{grantMsg}</p>}
                                </CardContent>
                            </Card>

                            {/* User List */}
                            <Card>
                                <CardHeader>
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="flex items-center gap-2 text-lg">
                                            <Users className="w-5 h-5" /> All Users
                                        </CardTitle>
                                        <Button variant="outline" size="sm" onClick={fetchUsers} disabled={usersLoading}>
                                            {usersLoading ? 'Loading...' : 'Refresh'}
                                        </Button>
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid md:grid-cols-4 gap-2 mb-3">
                                        <Input
                                            placeholder="Search by username/email"
                                            value={userSearchTerm}
                                            onChange={(e) => setUserSearchTerm(e.target.value)}
                                        />
                                        <select
                                            className="h-10 rounded-md border bg-background px-3 text-sm"
                                            value={userRoleFilter}
                                            onChange={(e) => setUserRoleFilter(e.target.value)}
                                        >
                                            <option value="all">All roles</option>
                                            <option value="student">Student</option>
                                            <option value="admin">Admin</option>
                                        </select>
                                        <select
                                            className="h-10 rounded-md border bg-background px-3 text-sm"
                                            value={userStatusFilter}
                                            onChange={(e) => setUserStatusFilter(e.target.value)}
                                        >
                                            <option value="all">All status</option>
                                            <option value="active">Active</option>
                                            <option value="blocked">Blocked</option>
                                        </select>
                                        <div className="flex gap-2">
                                            <Button size="sm" onClick={handleApplyUserFilters}>Apply</Button>
                                            <Button size="sm" variant="outline" onClick={handleResetUserFilters}>Reset</Button>
                                        </div>
                                    </div>

                                    <div className="rounded-lg border p-3 mb-3 bg-muted/20">
                                        <p className="text-xs font-medium text-muted-foreground mb-2">System Lifecycle Controls</p>
                                        <div className="grid md:grid-cols-4 gap-2">
                                            <select
                                                className="h-10 rounded-md border bg-background px-3 text-sm"
                                                value={systemScope}
                                                onChange={(e) => setSystemScope(e.target.value as 'all' | 'user')}
                                            >
                                                <option value="all">Scope: All users</option>
                                                <option value="user">Scope: Single user</option>
                                            </select>
                                            <Input
                                                type="number"
                                                placeholder="User ID (required for user scope)"
                                                value={systemUserId}
                                                onChange={(e) => setSystemUserId(e.target.value)}
                                                disabled={systemScope !== 'user'}
                                            />
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => runSystemAction('resetAttempts')}
                                                disabled={systemActionLoading || (systemScope === 'user' && !systemUserId)}
                                            >
                                                Reset Attempts
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => runSystemAction('clearAnalytics')}
                                                disabled={systemActionLoading || (systemScope === 'user' && !systemUserId)}
                                            >
                                                Clear Analytics
                                            </Button>
                                        </div>
                                        <div className="mt-2 flex justify-end">
                                            <Button
                                                size="sm"
                                                onClick={() => runSystemAction('rerunEvaluation')}
                                                disabled={systemActionLoading || (systemScope === 'user' && !systemUserId)}
                                            >
                                                Re-run Evaluation
                                            </Button>
                                        </div>
                                    </div>

                                    {userActionMessage && <p className="text-xs text-primary mb-2">{userActionMessage}</p>}

                                    {usersLoading ? (
                                        <p className="text-sm text-muted-foreground animate-pulse text-center py-4">Loading users...</p>
                                    ) : userList.length === 0 ? (
                                        <p className="text-sm text-muted-foreground text-center py-4">No users found</p>
                                    ) : (
                                        <div className="overflow-x-auto">
                                            <table className="w-full text-sm">
                                                <thead>
                                                    <tr className="border-b text-left text-muted-foreground">
                                                        <th className="pb-2 pr-4">ID</th>
                                                        <th className="pb-2 pr-4">Username</th>
                                                        <th className="pb-2 pr-4">Email</th>
                                                        <th className="pb-2 pr-4">Role</th>
                                                        <th className="pb-2 pr-4">Status</th>
                                                        <th className="pb-2 pr-4 text-right">Attempts</th>
                                                        <th className="pb-2 pr-4 text-right">Tokens</th>
                                                        <th className="pb-2 pr-4 text-right">Actions</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {userList.map((u: any) => (
                                                        <tr key={u.id || u.user_id} className="border-b last:border-0 hover:bg-muted/50">
                                                            <td className="py-2 pr-4 text-muted-foreground">{u.id || u.user_id}</td>
                                                            <td className="py-2 pr-4 font-medium">{u.username}</td>
                                                            <td className="py-2 pr-4 text-muted-foreground">{u.email || '—'}</td>
                                                            <td className="py-2 pr-4">
                                                                <Badge variant={u.role === 'admin' ? 'default' : 'secondary'} className="text-[10px]">
                                                                    {u.role || 'student'}
                                                                </Badge>
                                                            </td>
                                                            <td className="py-2 pr-4">
                                                                <Badge variant={u.is_active ? 'outline' : 'secondary'} className="text-[10px]">
                                                                    {u.is_active ? 'Active' : 'Blocked'}
                                                                </Badge>
                                                            </td>
                                                            <td className="py-2 pr-4 text-right">{u.test_attempt_count ?? '—'}</td>
                                                            <td className="py-2 pr-4 text-right font-medium">
                                                                {u.available_tokens ?? u.total_tokens ?? '—'}
                                                            </td>
                                                            <td className="py-2 pr-4">
                                                                <div className="flex justify-end gap-1">
                                                                    <Button
                                                                        size="sm"
                                                                        variant="outline"
                                                                        onClick={() => handleToggleUserBlock(Number(u.id || u.user_id), Boolean(u.is_active))}
                                                                        disabled={userActionLoadingId === Number(u.id || u.user_id)}
                                                                    >
                                                                        {u.is_active ? 'Block' : 'Unblock'}
                                                                    </Button>
                                                                    <Button
                                                                        size="sm"
                                                                        variant="outline"
                                                                        onClick={() => handleToggleUserRole(Number(u.id || u.user_id), String(u.role || 'student'))}
                                                                        disabled={userActionLoadingId === Number(u.id || u.user_id)}
                                                                    >
                                                                        {u.role === 'admin' ? 'Make Student' : 'Make Admin'}
                                                                    </Button>
                                                                    <Button
                                                                        size="sm"
                                                                        variant="outline"
                                                                        onClick={() => handleResetUserProgress(Number(u.id || u.user_id))}
                                                                        disabled={userActionLoadingId === Number(u.id || u.user_id)}
                                                                    >
                                                                        Reset Progress
                                                                    </Button>
                                                                </div>
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </div>
                    )}

                    {/* ===== FEEDBACK QUEUE TAB ===== */}
                    {activeTab === 'feedback' && (
                        <Card>
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <CardTitle className="flex items-center gap-2 text-lg">
                                        <MessageSquare className="w-5 h-5" /> Question Feedback
                                    </CardTitle>
                                    <Button variant="outline" size="sm" onClick={fetchFeedback} disabled={feedbackLoading}>
                                        {feedbackLoading ? 'Loading...' : 'Refresh'}
                                    </Button>
                                </div>
                                <CardDescription>Review flagged questions. Resolving rewards the user with 2 tokens.</CardDescription>
                            </CardHeader>
                            <CardContent>
                                {feedbackLoading ? (
                                    <p className="text-sm text-muted-foreground animate-pulse text-center py-4">Loading feedback...</p>
                                ) : feedbackList.length === 0 ? (
                                    <p className="text-sm text-muted-foreground text-center py-4">No feedback submissions yet</p>
                                ) : (
                                    <div className="space-y-3">
                                        {feedbackList.map((f: any) => (
                                            <div key={f.id} className={`p-4 rounded-lg border ${f.is_resolved ? 'opacity-60' : ''}`}>
                                                <div className="flex items-start justify-between gap-3">
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2 mb-1">
                                                            <Badge variant="outline" className="text-[10px]">{f.category}</Badge>
                                                            <span className="text-xs text-muted-foreground">Q#{f.question}</span>
                                                            {f.is_resolved && (
                                                                <Badge className="text-[10px] bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300">
                                                                    <CheckCircle className="w-3 h-3 mr-0.5" /> Resolved
                                                                </Badge>
                                                            )}
                                                        </div>
                                                        <p className="text-sm">{f.comment}</p>
                                                        <p className="text-xs text-muted-foreground mt-1">{new Date(f.created_at).toLocaleString()}</p>
                                                    </div>
                                                    {!f.is_resolved && (
                                                        <Button size="sm" variant="outline" onClick={() => handleResolveFeedback(f.id)}>
                                                            <CheckCircle className="w-4 h-4 mr-1" /> Resolve
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}

                    {activeTab === 'questions' && (
                        <div className="space-y-4">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Question Bank Control</CardTitle>
                                    <CardDescription>Server-side listing with trust controls, search, and filters.</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <details className="mb-4 rounded-lg border p-3 bg-muted/20">
                                        <summary className="cursor-pointer text-sm font-medium">Manual Create Question</summary>
                                        <div className="grid md:grid-cols-2 gap-3 mt-3">
                                        <Input
                                            placeholder="Question text"
                                            value={createForm.question_text}
                                            onChange={(e) => setCreateForm({ ...createForm, question_text: e.target.value })}
                                        />
                                        <Input
                                            type="number"
                                            placeholder="Year"
                                            value={createForm.year}
                                            onChange={(e) => setCreateForm({ ...createForm, year: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Option A"
                                            value={createForm.option_a}
                                            onChange={(e) => setCreateForm({ ...createForm, option_a: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Option B"
                                            value={createForm.option_b}
                                            onChange={(e) => setCreateForm({ ...createForm, option_b: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Option C"
                                            value={createForm.option_c}
                                            onChange={(e) => setCreateForm({ ...createForm, option_c: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Option D"
                                            value={createForm.option_d}
                                            onChange={(e) => setCreateForm({ ...createForm, option_d: e.target.value })}
                                        />
                                        <select
                                            className="h-10 rounded-md border bg-background px-3 text-sm"
                                            value={createForm.subject}
                                            onChange={(e) => setCreateForm({ ...createForm, subject: e.target.value })}
                                        >
                                            <option value="">Select subject</option>
                                            {questionSubjects.map((s: any) => (
                                                <option key={s.id} value={s.id}>{s.name}</option>
                                            ))}
                                        </select>
                                        <select
                                            className="h-10 rounded-md border bg-background px-3 text-sm"
                                            value={createForm.topic}
                                            onChange={(e) => setCreateForm({ ...createForm, topic: e.target.value })}
                                        >
                                            <option value="">Optional topic</option>
                                            {questionTopics
                                                .filter((t: any) => !createForm.subject || String(t.subject) === createForm.subject)
                                                .map((t: any) => (
                                                    <option key={t.id} value={t.id}>{t.name}</option>
                                                ))}
                                        </select>
                                        <select
                                            className="h-10 rounded-md border bg-background px-3 text-sm"
                                            value={createForm.correct_answer}
                                            onChange={(e) => setCreateForm({ ...createForm, correct_answer: e.target.value })}
                                        >
                                            <option value="A">Correct: A</option>
                                            <option value="B">Correct: B</option>
                                            <option value="C">Correct: C</option>
                                            <option value="D">Correct: D</option>
                                        </select>
                                        <select
                                            className="h-10 rounded-md border bg-background px-3 text-sm"
                                            value={createForm.difficulty}
                                            onChange={(e) => setCreateForm({ ...createForm, difficulty: e.target.value })}
                                        >
                                            <option value="easy">Easy</option>
                                            <option value="medium">Medium</option>
                                            <option value="hard">Hard</option>
                                        </select>
                                        <Input
                                            type="number"
                                            placeholder="Paper (1/2)"
                                            value={createForm.paper}
                                            onChange={(e) => setCreateForm({ ...createForm, paper: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Concept ID (optional)"
                                            value={createForm.concept_id}
                                            onChange={(e) => setCreateForm({ ...createForm, concept_id: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Book name (optional)"
                                            value={createForm.book_name}
                                            onChange={(e) => setCreateForm({ ...createForm, book_name: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Chapter (optional)"
                                            value={createForm.chapter}
                                            onChange={(e) => setCreateForm({ ...createForm, chapter: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Page number (optional)"
                                            value={createForm.page_number}
                                            onChange={(e) => setCreateForm({ ...createForm, page_number: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Related PYQ IDs (e.g. 12,45,90)"
                                            value={createForm.related_question_ids}
                                            onChange={(e) => setCreateForm({ ...createForm, related_question_ids: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Explanation (optional)"
                                            value={createForm.explanation}
                                            onChange={(e) => setCreateForm({ ...createForm, explanation: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Reference excerpt (optional)"
                                            value={createForm.reference_text}
                                            onChange={(e) => setCreateForm({ ...createForm, reference_text: e.target.value })}
                                        />
                                        </div>
                                        <div className="flex gap-2 mt-3">
                                        <Button size="sm" onClick={handleCreateQuestion} disabled={createLoading}>
                                            {createLoading ? 'Creating...' : 'Create Question'}
                                        </Button>
                                        </div>
                                    </details>

                                    <details className="rounded-lg border p-3 mb-4 bg-muted/20">
                                        <summary className="cursor-pointer text-sm font-medium">Bulk Import Preview (JSON/CSV)</summary>
                                        <div className="space-y-3 mt-3">
                                        <div className="flex gap-2 items-center">
                                            <select
                                                className="h-9 rounded-md border bg-background px-3 text-sm"
                                                value={importFormat}
                                                onChange={(e) => setImportFormat(e.target.value as 'json' | 'csv')}
                                            >
                                                <option value="json">JSON</option>
                                                <option value="csv">CSV</option>
                                            </select>
                                            <Button size="sm" variant="outline" onClick={handleImportPreview} disabled={importPreviewLoading}>
                                                {importPreviewLoading ? 'Previewing...' : 'Run Import Preview'}
                                            </Button>
                                        </div>
                                        <textarea
                                            className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-24 resize-y"
                                            placeholder={importFormat === 'json' ? 'Paste JSON array/object for preview' : 'Paste CSV text with headers for preview'}
                                            value={importPayload}
                                            onChange={(e) => setImportPayload(e.target.value)}
                                        />
                                        {importPreviewResult && (
                                            <div className="text-xs rounded-md border p-2 bg-background space-y-1">
                                                <p>Total: {importPreviewResult.total_rows} | Valid: {importPreviewResult.valid_rows} | Invalid: {importPreviewResult.invalid_rows}</p>
                                                <p>To Create: {importPreviewResult.to_create} | To Update: {importPreviewResult.to_update}</p>
                                                {Array.isArray(importPreviewResult.errors) && importPreviewResult.errors.length > 0 && (
                                                    <div className="max-h-28 overflow-auto text-red-600">
                                                        {importPreviewResult.errors.slice(0, 10).map((e: any, idx: number) => (
                                                            <p key={idx}>Row {e.row}: {typeof e.errors === 'string' ? e.errors : JSON.stringify(e.errors)}</p>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                        </div>
                                    </details>

                                    <details className="rounded-lg border p-3 mb-4 bg-muted/20">
                                        <summary className="cursor-pointer text-sm font-medium">PYQ Extraction Queue (Word/PDF)</summary>
                                        <div className="space-y-3 mt-3">
                                        <div className="flex gap-2 flex-wrap items-center">
                                            <Input
                                                type="file"
                                                accept=".doc,.docx,.pdf"
                                                onChange={(e) => setExtractionFile(e.target.files?.[0] || null)}
                                            />
                                            <Button size="sm" onClick={handleExtractionUpload} disabled={extractionLoading || !extractionFile}>
                                                {extractionLoading ? 'Uploading...' : 'Queue Extraction'}
                                            </Button>
                                            <Button size="sm" variant="outline" onClick={fetchExtractionJobs} disabled={extractionJobsLoading}>
                                                {extractionJobsLoading ? 'Refreshing...' : 'Refresh Jobs'}
                                            </Button>
                                        </div>
                                        {extractionJobs.length > 0 && (
                                            <div className="space-y-2 max-h-44 overflow-auto">
                                                {extractionJobs.map((job: any) => (
                                                    <div key={job.id} className="rounded-md border p-2 text-xs flex items-center justify-between gap-2">
                                                        <div className="min-w-0">
                                                            <p className="font-medium truncate">#{job.id} {job.source_filename || 'Untitled'}</p>
                                                            <p className="text-muted-foreground">{job.job_type} • {job.status}</p>
                                                        </div>
                                                        <div className="flex gap-2">
                                                            <Button size="sm" variant="outline" onClick={() => fetchExtractionItems(Number(job.id))}>
                                                                Review
                                                            </Button>
                                                            <Button size="sm" variant="outline" onClick={() => handleExtractionRetry(Number(job.id))}>
                                                                Retry
                                                            </Button>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        )}

                                        {selectedExtractionJobId && (
                                            <div className="rounded-md border p-2 bg-background space-y-2">
                                                <p className="text-xs font-medium">Extraction Items for Job #{selectedExtractionJobId}</p>
                                                {extractionItemsLoading ? (
                                                    <p className="text-xs text-muted-foreground">Loading items...</p>
                                                ) : extractionItems.length === 0 ? (
                                                    <p className="text-xs text-muted-foreground">No extraction items found for this job.</p>
                                                ) : (
                                                    <div className="space-y-2 max-h-64 overflow-auto">
                                                        {extractionItems.map((item: any) => (
                                                            <div key={item.id} className="rounded-md border p-2 text-xs space-y-2">
                                                                <div className="flex items-center justify-between gap-2">
                                                                    <p className="font-medium">Item #{item.id} • {item.status}</p>
                                                                    <div className="flex gap-1 flex-wrap">
                                                                        <Button size="sm" variant="outline" onClick={() => runExtractionItemAction('autotag', Number(item.id))}>Auto-tag</Button>
                                                                        <Button size="sm" variant="outline" onClick={() => runExtractionItemAction('approve', Number(item.id))}>Approve</Button>
                                                                        <Button size="sm" variant="outline" onClick={() => runExtractionItemAction('reject', Number(item.id))}>Reject</Button>
                                                                        <Button size="sm" onClick={() => runExtractionItemAction('publish', Number(item.id))}>Publish</Button>
                                                                        <Button size="sm" variant="outline" onClick={() => beginExtractionItemEdit(item)}>Edit</Button>
                                                                    </div>
                                                                </div>

                                                                {editingExtractionItemId === Number(item.id) && editingExtractionItem ? (
                                                                    <div className="space-y-2">
                                                                        <textarea
                                                                            className="w-full rounded-md border bg-background px-2 py-1 text-xs min-h-16 resize-y"
                                                                            value={editingExtractionItem.question_text || ''}
                                                                            onChange={(e) => setEditingExtractionItem({ ...editingExtractionItem, question_text: e.target.value })}
                                                                            placeholder="Question text"
                                                                        />
                                                                        <div className="grid md:grid-cols-2 gap-2">
                                                                            <Input value={editingExtractionItem.option_a || ''} onChange={(e) => setEditingExtractionItem({ ...editingExtractionItem, option_a: e.target.value })} placeholder="Option A" />
                                                                            <Input value={editingExtractionItem.option_b || ''} onChange={(e) => setEditingExtractionItem({ ...editingExtractionItem, option_b: e.target.value })} placeholder="Option B" />
                                                                            <Input value={editingExtractionItem.option_c || ''} onChange={(e) => setEditingExtractionItem({ ...editingExtractionItem, option_c: e.target.value })} placeholder="Option C" />
                                                                            <Input value={editingExtractionItem.option_d || ''} onChange={(e) => setEditingExtractionItem({ ...editingExtractionItem, option_d: e.target.value })} placeholder="Option D" />
                                                                            <Input value={editingExtractionItem.correct_answer || ''} onChange={(e) => setEditingExtractionItem({ ...editingExtractionItem, correct_answer: e.target.value })} placeholder="Correct (A/B/C/D)" />
                                                                            <Input type="number" value={editingExtractionItem.year || ''} onChange={(e) => setEditingExtractionItem({ ...editingExtractionItem, year: Number(e.target.value) || null })} placeholder="Year" />
                                                                            <Input type="number" value={editingExtractionItem.paper || ''} onChange={(e) => setEditingExtractionItem({ ...editingExtractionItem, paper: Number(e.target.value) || 0 })} placeholder="Paper" />
                                                                            <select className="h-9 rounded-md border bg-background px-3 text-xs" value={String(editingExtractionItem.subject || '')} onChange={(e) => setEditingExtractionItem({ ...editingExtractionItem, subject: Number(e.target.value) || null, topic: null })}>
                                                                                <option value="">Subject</option>
                                                                                {questionSubjects.map((s: any) => (
                                                                                    <option key={s.id} value={s.id}>{s.name}</option>
                                                                                ))}
                                                                            </select>
                                                                            <select className="h-9 rounded-md border bg-background px-3 text-xs" value={String(editingExtractionItem.topic || '')} onChange={(e) => setEditingExtractionItem({ ...editingExtractionItem, topic: Number(e.target.value) || null })}>
                                                                                <option value="">Topic</option>
                                                                                {questionTopics.filter((t: any) => !editingExtractionItem.subject || Number(t.subject) === Number(editingExtractionItem.subject)).map((t: any) => (
                                                                                    <option key={t.id} value={t.id}>{t.name}</option>
                                                                                ))}
                                                                            </select>
                                                                        </div>
                                                                        <textarea
                                                                            className="w-full rounded-md border bg-background px-2 py-1 text-xs min-h-12 resize-y"
                                                                            value={editingExtractionItem.explanation || ''}
                                                                            onChange={(e) => setEditingExtractionItem({ ...editingExtractionItem, explanation: e.target.value })}
                                                                            placeholder="Explanation"
                                                                        />
                                                                        <div className="flex gap-2">
                                                                            <Button size="sm" onClick={() => saveExtractionItemEdit(Number(item.id))}>Save Item</Button>
                                                                            <Button size="sm" variant="outline" onClick={cancelExtractionItemEdit}>Cancel</Button>
                                                                        </div>
                                                                    </div>
                                                                ) : (
                                                                    <div>
                                                                        <p className="line-clamp-2">{item.question_text || item.raw_text || 'No extracted text yet'}</p>
                                                                        <p className="text-muted-foreground">Year: {item.year || '—'} • Paper: {item.paper || '—'} • Subject: {item.subject_name || '—'} • Topic: {item.topic_name || '—'}</p>
                                                                    </div>
                                                                )}
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                        </div>
                                    </details>

                                    <details className="rounded-lg border p-3 mb-4 bg-muted/20">
                                        <summary className="cursor-pointer text-sm font-medium">AI Prompt Editor and Version History</summary>
                                        <div className="space-y-3 mt-3">
                                        <div className="grid md:grid-cols-2 gap-2">
                                            <Input
                                                placeholder="Prompt version name"
                                                value={aiPromptName}
                                                onChange={(e) => setAiPromptName(e.target.value)}
                                            />
                                            <Button size="sm" onClick={handleCreateAiPromptVersion} disabled={aiPromptSaving}>
                                                {aiPromptSaving ? 'Saving...' : 'Save New Prompt Version'}
                                            </Button>
                                        </div>
                                        <textarea
                                            className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-20 resize-y"
                                            placeholder="Prompt template"
                                            value={aiPromptText}
                                            onChange={(e) => setAiPromptText(e.target.value)}
                                        />
                                        {aiPromptVersions.length === 0 ? (
                                            <p className="text-xs text-muted-foreground">No prompt versions yet.</p>
                                        ) : (
                                            <div className="space-y-2 max-h-36 overflow-auto">
                                                {aiPromptVersions.slice(0, 20).map((version: any) => (
                                                    <div key={version.id} className="rounded-md border p-2 text-xs flex items-center justify-between gap-2">
                                                        <div className="min-w-0">
                                                            <p className="font-medium truncate">{version.name}</p>
                                                            <p className="text-muted-foreground">{new Date(version.created_at).toLocaleString()} {version.created_by_username ? `• ${version.created_by_username}` : ''}</p>
                                                        </div>
                                                        {version.is_active ? (
                                                            <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">Active</Badge>
                                                        ) : (
                                                            <Button size="sm" variant="outline" onClick={() => handleActivatePromptVersion(Number(version.id))}>Activate</Button>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                        </div>
                                    </details>

                                    <div className="grid md:grid-cols-6 gap-3">
                                        <Input
                                            placeholder="Search keyword or question ID"
                                            value={questionSearch}
                                            onChange={(e) => setQuestionSearch(e.target.value)}
                                            onKeyDown={handleQuestionSearchKeyDown}
                                        />
                                        <select
                                            className="h-10 rounded-md border bg-background px-3 text-sm"
                                            value={questionSubject}
                                            onChange={(e) => setQuestionSubject(e.target.value)}
                                        >
                                            <option value="">All subjects</option>
                                            {questionSubjects.map((s: any) => (
                                                <option key={s.id} value={s.id}>{s.name}</option>
                                            ))}
                                        </select>
                                        <select
                                            className="h-10 rounded-md border bg-background px-3 text-sm"
                                            value={questionDifficulty}
                                            onChange={(e) => setQuestionDifficulty(e.target.value)}
                                        >
                                            <option value="">All difficulty</option>
                                            <option value="easy">Easy</option>
                                            <option value="medium">Medium</option>
                                            <option value="hard">Hard</option>
                                        </select>
                                        <Input
                                            type="number"
                                            placeholder="Year"
                                            value={questionYear}
                                            onChange={(e) => setQuestionYear(e.target.value)}
                                        />
                                        <Button size="sm" onClick={handleQuestionFilterApply}>Search</Button>
                                        <Button size="sm" variant="outline" onClick={handleQuestionFilterReset}>Reset</Button>
                                    </div>
                                    <div className="mt-3">
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            onClick={() => setShowAdvancedQuestionFilters((prev) => !prev)}
                                        >
                                            {showAdvancedQuestionFilters ? 'Hide Advanced Filters' : 'Show Advanced Filters'}
                                        </Button>
                                    </div>
                                    {showAdvancedQuestionFilters && (
                                        <div className="grid md:grid-cols-4 gap-3 mt-3">
                                            <select
                                                className="h-10 rounded-md border bg-background px-3 text-sm"
                                                value={questionVerified}
                                                onChange={(e) => setQuestionVerified(e.target.value)}
                                            >
                                                <option value="all">All trust states</option>
                                                <option value="verified">Verified only</option>
                                                <option value="unverified">Unverified only</option>
                                            </select>
                                            <select
                                                className="h-10 rounded-md border bg-background px-3 text-sm"
                                                value={questionFlagged}
                                                onChange={(e) => setQuestionFlagged(e.target.value)}
                                            >
                                                <option value="all">All feedback states</option>
                                                <option value="flagged">Flagged only</option>
                                                <option value="clean">Without flags</option>
                                            </select>
                                            <Input
                                                type="number"
                                                placeholder="Min accuracy %"
                                                value={questionAccuracyMin}
                                                onChange={(e) => setQuestionAccuracyMin(e.target.value)}
                                            />
                                            <Input
                                                type="number"
                                                placeholder="Max accuracy %"
                                                value={questionAccuracyMax}
                                                onChange={(e) => setQuestionAccuracyMax(e.target.value)}
                                            />
                                        </div>
                                    )}
                                    <div className="mt-2 text-xs text-muted-foreground">
                                        Tip: Press Enter in search field to run search quickly.
                                    </div>
                                    <div className="mt-2 flex flex-wrap items-center gap-2">
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => setCompactQuestionPreview((prev) => !prev)}
                                        >
                                            {compactQuestionPreview ? 'Compact Preview: On' : 'Compact Preview: Off'}
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => setExpandedQuestionIds([])}
                                            disabled={expandedQuestionIds.length === 0}
                                        >
                                            Collapse All
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={selectDuplicateQuestionsOnPage}
                                        >
                                            Select Duplicate Rows
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="text-lg">Questions ({questionTotal})</CardTitle>
                                        <div className="flex gap-2">
                                            <Button size="sm" variant="outline" onClick={() => fetchQuestions()} disabled={questionsLoading}>
                                                {questionsLoading ? 'Loading...' : 'Refresh'}
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={toggleSelectAllVisibleQuestions}
                                                disabled={questionsLoading || questionList.length === 0}
                                            >
                                                {questionList.length > 0 && questionList.every((q: any) => selectedQuestionIds.includes(Number(q.id))) ? 'Unselect Visible' : 'Select Visible'}
                                            </Button>
                                        </div>
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    <div className="mb-3 flex flex-wrap items-center gap-2">
                                        <Badge variant="outline">Selected: {selectedQuestionIds.length}</Badge>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={runBulkFormatFixAction}
                                            disabled={bulkActionLoading || selectedQuestionIds.length === 0}
                                        >
                                            {bulkActionLoading ? 'Formatting...' : 'Auto Format Selected'}
                                        </Button>
                                        <Button
                                            size="sm"
                                            onClick={() => runBulkVerifyAction(true)}
                                            disabled={bulkActionLoading || selectedQuestionIds.length === 0}
                                        >
                                            Bulk Verify
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => runBulkVerifyAction(false)}
                                            disabled={bulkActionLoading || selectedQuestionIds.length === 0}
                                        >
                                            Bulk Unverify
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            onClick={() => setSelectedQuestionIds([])}
                                            disabled={bulkActionLoading || selectedQuestionIds.length === 0}
                                        >
                                            Clear Selection
                                        </Button>
                                    </div>

                                    <details className="mb-4 rounded-lg border p-3 bg-muted/20">
                                        <summary className="cursor-pointer text-sm font-medium">Bulk Metadata Edit</summary>
                                        <div className="space-y-3 mt-3">
                                        <p className="text-xs font-medium text-muted-foreground">Select questions first, then apply bulk actions.</p>
                                        <div className="grid md:grid-cols-5 gap-2">
                                            <select
                                                className="h-9 rounded-md border bg-background px-3 text-sm"
                                                value={bulkMetaSubject}
                                                onChange={(e) => {
                                                    setBulkMetaSubject(e.target.value);
                                                    setBulkMetaTopic('');
                                                }}
                                            >
                                                <option value="">No subject change</option>
                                                {questionSubjects.map((s: any) => (
                                                    <option key={s.id} value={s.id}>{s.name}</option>
                                                ))}
                                            </select>
                                            <select
                                                className="h-9 rounded-md border bg-background px-3 text-sm"
                                                value={bulkMetaTopic}
                                                onChange={(e) => setBulkMetaTopic(e.target.value)}
                                            >
                                                <option value="">No topic change</option>
                                                {questionTopics
                                                    .filter((t: any) => !bulkMetaSubject || String(t.subject) === bulkMetaSubject)
                                                    .map((t: any) => (
                                                        <option key={t.id} value={t.id}>{t.name}</option>
                                                    ))}
                                            </select>
                                            <select
                                                className="h-9 rounded-md border bg-background px-3 text-sm"
                                                value={bulkMetaDifficulty}
                                                onChange={(e) => setBulkMetaDifficulty(e.target.value)}
                                            >
                                                <option value="">No difficulty change</option>
                                                <option value="easy">Easy</option>
                                                <option value="medium">Medium</option>
                                                <option value="hard">Hard</option>
                                            </select>
                                            <Input
                                                type="number"
                                                placeholder="Year"
                                                value={bulkMetaYear}
                                                onChange={(e) => setBulkMetaYear(e.target.value)}
                                            />
                                            <Input
                                                type="number"
                                                placeholder="Paper"
                                                value={bulkMetaPaper}
                                                onChange={(e) => setBulkMetaPaper(e.target.value)}
                                            />
                                        </div>
                                        <div className="flex gap-2 flex-wrap items-center">
                                            <Button size="sm" onClick={handleBulkMetadataUpdate} disabled={bulkMetaLoading || selectedQuestionIds.length === 0}>
                                                {bulkMetaLoading ? 'Updating...' : 'Apply Bulk Metadata'}
                                            </Button>
                                            <Input
                                                className="max-w-52"
                                                placeholder="Type DELETE for bulk delete"
                                                value={bulkDeleteConfirm}
                                                onChange={(e) => setBulkDeleteConfirm(e.target.value)}
                                            />
                                            <Button size="sm" variant="destructive" onClick={handleBulkDelete} disabled={bulkDeleteLoading || selectedQuestionIds.length === 0 || bulkDeleteConfirm !== 'DELETE'}>
                                                {bulkDeleteLoading ? 'Deleting...' : 'Bulk Delete (Soft)'}
                                            </Button>
                                        </div>
                                        </div>
                                    </details>

                                    {questionsLoading ? (
                                        <p className="text-sm text-muted-foreground animate-pulse text-center py-4">Loading questions...</p>
                                    ) : questionList.length === 0 ? (
                                        <p className="text-sm text-muted-foreground text-center py-4">No questions found for selected filters</p>
                                    ) : (
                                        <div className="space-y-2">
                                            {questionList.map((q: any) => (
                                                <div key={q.id} className="border rounded-lg p-3">
                                                    <div className="flex items-start gap-3">
                                                    <input
                                                        type="checkbox"
                                                        className="mt-1 h-4 w-4"
                                                        checked={selectedQuestionIds.includes(Number(q.id))}
                                                        onChange={() => toggleQuestionSelection(Number(q.id))}
                                                    />
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                                                            <Badge variant="outline">Q#{q.id}</Badge>
                                                            <Badge variant="secondary">{q.subject_name || 'Unknown subject'}</Badge>
                                                            {q.topic_name && <Badge variant="outline">{q.topic_name}</Badge>}
                                                            {q.difficulty && <Badge variant="outline" className="capitalize">{q.difficulty}</Badge>}
                                                            {q.year && <Badge variant="outline">{q.year}</Badge>}
                                                            {q.accuracy !== null && q.accuracy !== undefined && (
                                                                <Badge variant="outline">Acc: {Number(q.accuracy).toFixed(1)}%</Badge>
                                                            )}
                                                            {q.concept_id && <Badge variant="outline">Concept: {q.concept_id}</Badge>}
                                                            {(() => {
                                                                const normalized = normalizeQuestionText(q.question_text || '');
                                                                const duplicateCount = normalized ? duplicateQuestionInfo[normalized] || 0 : 0;
                                                                if (duplicateCount <= 1) return null;
                                                                return (
                                                                    <Badge className="bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300">
                                                                        Possible duplicate x{duplicateCount}
                                                                    </Badge>
                                                                );
                                                            })()}
                                                            {q.is_verified_by_admin ? (
                                                                <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">Verified</Badge>
                                                            ) : (
                                                                <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">Unverified</Badge>
                                                            )}
                                                        </div>
                                                        {editingQuestionId === Number(q.id) ? (
                                                            <div className="space-y-2 mt-2">
                                                                <textarea
                                                                    className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-20 resize-y"
                                                                    value={editingForm.question_text}
                                                                    onChange={(e) => setEditingForm({ ...editingForm, question_text: e.target.value })}
                                                                    placeholder="Question text"
                                                                />
                                                                <div className="grid md:grid-cols-2 gap-2">
                                                                    <Input
                                                                        value={editingForm.option_a}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, option_a: e.target.value })}
                                                                        placeholder="Option A"
                                                                    />
                                                                    <Input
                                                                        value={editingForm.option_b}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, option_b: e.target.value })}
                                                                        placeholder="Option B"
                                                                    />
                                                                    <Input
                                                                        value={editingForm.option_c}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, option_c: e.target.value })}
                                                                        placeholder="Option C"
                                                                    />
                                                                    <Input
                                                                        value={editingForm.option_d}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, option_d: e.target.value })}
                                                                        placeholder="Option D"
                                                                    />
                                                                    <Input
                                                                        value={editingForm.correct_answer}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, correct_answer: e.target.value })}
                                                                        placeholder="Correct answer (A/B/C/D)"
                                                                    />
                                                                    <Input
                                                                        type="number"
                                                                        value={editingForm.year}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, year: e.target.value })}
                                                                        placeholder="Year"
                                                                    />
                                                                    <Input
                                                                        type="number"
                                                                        value={editingForm.paper}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, paper: e.target.value })}
                                                                        placeholder="Paper (1/2)"
                                                                    />
                                                                    <select
                                                                        className="h-10 rounded-md border bg-background px-3 text-sm"
                                                                        value={editingForm.subject}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, subject: e.target.value, topic: '' })}
                                                                    >
                                                                        <option value="">Select subject</option>
                                                                        {questionSubjects.map((s: any) => (
                                                                            <option key={s.id} value={s.id}>{s.name}</option>
                                                                        ))}
                                                                    </select>
                                                                    <select
                                                                        className="h-10 rounded-md border bg-background px-3 text-sm"
                                                                        value={editingForm.topic}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, topic: e.target.value })}
                                                                    >
                                                                        <option value="">Optional topic</option>
                                                                        {questionTopics
                                                                            .filter((t: any) => !editingForm.subject || String(t.subject) === editingForm.subject)
                                                                            .map((t: any) => (
                                                                                <option key={t.id} value={t.id}>{t.name}</option>
                                                                            ))}
                                                                    </select>
                                                                    <select
                                                                        className="h-10 rounded-md border bg-background px-3 text-sm"
                                                                        value={editingForm.difficulty}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, difficulty: e.target.value })}
                                                                    >
                                                                        <option value="easy">Easy</option>
                                                                        <option value="medium">Medium</option>
                                                                        <option value="hard">Hard</option>
                                                                    </select>
                                                                    <Input
                                                                        value={editingForm.concept_id}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, concept_id: e.target.value })}
                                                                        placeholder="Concept ID"
                                                                    />
                                                                    <Input
                                                                        value={editingForm.book_name}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, book_name: e.target.value })}
                                                                        placeholder="Book name"
                                                                    />
                                                                    <Input
                                                                        value={editingForm.chapter}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, chapter: e.target.value })}
                                                                        placeholder="Chapter"
                                                                    />
                                                                    <Input
                                                                        value={editingForm.page_number}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, page_number: e.target.value })}
                                                                        placeholder="Page number"
                                                                    />
                                                                    <Input
                                                                        value={editingForm.related_question_ids}
                                                                        onChange={(e) => setEditingForm({ ...editingForm, related_question_ids: e.target.value })}
                                                                        placeholder="Related PYQ IDs (comma-separated)"
                                                                    />
                                                                </div>
                                                                <textarea
                                                                    className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-15 resize-y"
                                                                    value={editingForm.explanation}
                                                                    onChange={(e) => setEditingForm({ ...editingForm, explanation: e.target.value })}
                                                                    placeholder="Explanation"
                                                                />
                                                                <textarea
                                                                    className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-15 resize-y"
                                                                    value={editingForm.reference_text}
                                                                    onChange={(e) => setEditingForm({ ...editingForm, reference_text: e.target.value })}
                                                                    placeholder="Textbook reference excerpt"
                                                                />
                                                                <div className="flex gap-2">
                                                                    <Button size="sm" onClick={() => saveInlineEdit(Number(q.id))} disabled={savingEdit}>
                                                                        {savingEdit ? 'Saving...' : 'Save'}
                                                                    </Button>
                                                                    <Button size="sm" variant="outline" onClick={cancelInlineEdit} disabled={savingEdit}>
                                                                        Cancel
                                                                    </Button>
                                                                </div>
                                                            </div>
                                                        ) : (
                                                            <div className="space-y-1">
                                                                {(() => {
                                                                    const rowId = Number(q.id);
                                                                    const isExpanded = expandedQuestionIds.includes(rowId);
                                                                    const shouldClamp = compactQuestionPreview && !isExpanded;
                                                                    return (
                                                                        <>
                                                                            <p className={`text-sm whitespace-pre-wrap break-words leading-relaxed ${shouldClamp ? 'line-clamp-3' : ''}`}>
                                                                                {q.question_text}
                                                                            </p>
                                                                            <div className="flex items-center gap-2">
                                                                                {compactQuestionPreview && (
                                                                                    <Button
                                                                                        size="sm"
                                                                                        variant="ghost"
                                                                                        onClick={() => toggleQuestionExpanded(rowId)}
                                                                                        className="h-7 px-2 text-xs"
                                                                                    >
                                                                                        {isExpanded ? 'Show less' : 'Show full'}
                                                                                    </Button>
                                                                                )}
                                                                            </div>
                                                                        </>
                                                                    );
                                                                })()}
                                                                {(!compactQuestionPreview || expandedQuestionIds.includes(Number(q.id))) && (
                                                                    <div className="grid sm:grid-cols-2 gap-1 text-xs">
                                                                        {q.option_a && <p className="text-muted-foreground">A. {q.option_a}</p>}
                                                                        {q.option_b && <p className="text-muted-foreground">B. {q.option_b}</p>}
                                                                        {q.option_c && <p className="text-muted-foreground">C. {q.option_c}</p>}
                                                                        {q.option_d && <p className="text-muted-foreground">D. {q.option_d}</p>}
                                                                    </div>
                                                                )}
                                                                <p className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
                                                                    Current correct answer: {q.correct_answer || q.effective_answer || 'Not set'}
                                                                </p>
                                                                {q.book_name && <p className="text-xs text-muted-foreground">Ref: {q.book_name} {q.chapter ? `• ${q.chapter}` : ''} {q.page_number ? `• p.${q.page_number}` : ''}</p>}
                                                                {q.effective_answer && <p className="text-xs text-muted-foreground">AI/Admin Answer: {q.effective_answer}</p>}
                                                                {q.effective_explanation && <p className="text-xs text-muted-foreground whitespace-pre-wrap break-words">AI/Admin Explanation: {q.effective_explanation}</p>}
                                                            </div>
                                                        )}
                                                    </div>
                                                    </div>
                                                    <div className="mt-3 flex flex-wrap gap-2">
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => startInlineEdit(q)}
                                                            disabled={savingEdit && editingQuestionId === Number(q.id)}
                                                        >
                                                            Edit
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => handleDuplicateQuestion(Number(q.id))}
                                                        >
                                                            Duplicate
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant={q.is_verified_by_admin ? 'outline' : 'default'}
                                                            onClick={() => handleQuestionVerifyToggle(q.id, Boolean(q.is_verified_by_admin))}
                                                        >
                                                            {q.is_verified_by_admin ? 'Unverify' : 'Verify'}
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => handleArchiveQuestion(Number(q.id))}
                                                        >
                                                            Archive
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => handleAiOverridePrompt(Number(q.id))}
                                                        >
                                                            AI Override
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => handleToggleAiLock(Number(q.id), !Boolean(q.lock_answer), Boolean(q.lock_explanation))}
                                                        >
                                                            {q.lock_answer ? 'Unlock Ans' : 'Lock Ans'}
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => handleToggleAiLock(Number(q.id), Boolean(q.lock_answer), !Boolean(q.lock_explanation))}
                                                        >
                                                            {q.lock_explanation ? 'Unlock Exp' : 'Lock Exp'}
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => handleForceRegenerate(Number(q.id))}
                                                        >
                                                            Regenerate AI
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => handleLoadAiTimeline(Number(q.id))}
                                                        >
                                                            AI Timeline
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => handleFormatFix(Number(q.id))}
                                                        >
                                                            Fix Format
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="destructive"
                                                            onClick={() => handleDeleteQuestion(Number(q.id))}
                                                        >
                                                            Delete
                                                        </Button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {aiTimelineQuestionId && (
                                        <div className="mt-4 rounded-lg border p-3 bg-muted/20">
                                            <div className="flex items-center justify-between mb-2">
                                                <p className="text-xs font-medium">AI Timeline for Question #{aiTimelineQuestionId}</p>
                                                <Button size="sm" variant="outline" onClick={() => setAiTimelineQuestionId(null)}>Close</Button>
                                            </div>
                                            {aiTimelineLoading ? (
                                                <p className="text-xs text-muted-foreground">Loading timeline...</p>
                                            ) : aiTimelineRows.length === 0 ? (
                                                <p className="text-xs text-muted-foreground">No AI operations logged for this question.</p>
                                            ) : (
                                                <div className="space-y-1 max-h-36 overflow-auto">
                                                    {aiTimelineRows.map((row: any) => (
                                                        <div key={row.id} className="text-xs rounded-md border p-2 bg-background">
                                                            <p className="font-medium">{row.operation_type} • {row.provider || 'n/a'} • tokens: {row.tokens_used || 0}</p>
                                                            <p className="text-muted-foreground">{new Date(row.created_at).toLocaleString()} {row.prompt_version_name ? `• ${row.prompt_version_name}` : ''}</p>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    <div className="flex justify-between mt-4">
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => {
                                                const nextPage = Math.max(1, questionPage - 1);
                                                setQuestionPage(nextPage);
                                                fetchQuestions(nextPage);
                                            }}
                                            disabled={questionPage <= 1 || questionsLoading}
                                        >
                                            Previous
                                        </Button>
                                        <span className="text-xs text-muted-foreground self-center">Page {questionPage}</span>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => {
                                                const nextPage = questionPage + 1;
                                                setQuestionPage(nextPage);
                                                fetchQuestions(nextPage);
                                            }}
                                            disabled={!questionHasNext || questionsLoading}
                                        >
                                            Next
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    )}

                    {activeTab === 'tests' && (
                        <div className="space-y-4">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Tests Engine Control</CardTitle>
                                    <CardDescription>Create draft tests, assign questions, then publish/unpublish safely.</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                    <div className="grid md:grid-cols-2 gap-2">
                                        <Input placeholder="Test title" value={testForm.title} onChange={(e) => setTestForm({ ...testForm, title: e.target.value })} />
                                        <Input placeholder="Description" value={testForm.description} onChange={(e) => setTestForm({ ...testForm, description: e.target.value })} />
                                        <select className="h-10 rounded-md border bg-background px-3 text-sm" value={testForm.test_type} onChange={(e) => setTestForm({ ...testForm, test_type: e.target.value })}>
                                            <option value="mixed">Mixed</option>
                                            <option value="subject">Subject</option>
                                            <option value="topic">Topic</option>
                                            <option value="paper1">Paper 1</option>
                                            <option value="paper2">Paper 2</option>
                                            <option value="pyq_year">PYQ Year</option>
                                        </select>
                                        <Input type="number" placeholder="Time limit (minutes)" value={testForm.time_limit_minutes} onChange={(e) => setTestForm({ ...testForm, time_limit_minutes: e.target.value })} />
                                        <Input type="number" step="0.01" placeholder="Negative mark value" value={testForm.negative_mark_value} onChange={(e) => setTestForm({ ...testForm, negative_mark_value: e.target.value })} />
                                        <label className="h-10 rounded-md border bg-background px-3 text-sm flex items-center gap-2">
                                            <input type="checkbox" checked={testForm.negative_marking} onChange={(e) => setTestForm({ ...testForm, negative_marking: e.target.checked })} />
                                            Negative marking enabled
                                        </label>
                                    </div>
                                    <div className="rounded-md border p-3 bg-muted/20 space-y-2">
                                        <div className="flex gap-2">
                                            <Input placeholder="Search questions for test" value={testQuestionSearch} onChange={(e) => setTestQuestionSearch(e.target.value)} />
                                            <Button size="sm" variant="outline" onClick={fetchTestCandidateQuestions}>Search</Button>
                                        </div>
                                        <div className="max-h-44 overflow-auto space-y-1">
                                            {testCandidateQuestions.map((q: any) => (
                                                <label key={q.id} className="text-xs rounded-md border p-2 bg-background flex items-start gap-2">
                                                    <input type="checkbox" checked={selectedTestQuestionIds.includes(Number(q.id))} onChange={() => toggleTestQuestionSelection(Number(q.id))} />
                                                    <span className="line-clamp-2">#{q.id} {q.question_text}</span>
                                                </label>
                                            ))}
                                        </div>
                                        <p className="text-xs text-muted-foreground">Selected for manual test: {selectedTestQuestionIds.length}</p>
                                    </div>
                                    <Button onClick={handleCreateManualTest} disabled={testSaveLoading}>
                                        {testSaveLoading ? 'Saving...' : 'Create Manual Draft Test'}
                                    </Button>
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle>Published and Draft Tests</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    {adminTestsLoading ? (
                                        <p className="text-sm text-muted-foreground">Loading tests...</p>
                                    ) : adminTests.length === 0 ? (
                                        <p className="text-sm text-muted-foreground">No tests found.</p>
                                    ) : (
                                        <div className="space-y-2">
                                            {adminTests.map((t: any) => (
                                                <div key={t.id} className="rounded-md border p-3 flex items-center justify-between gap-3">
                                                    <div>
                                                        <p className="text-sm font-medium">#{t.id} {t.title}</p>
                                                        <p className="text-xs text-muted-foreground">{t.test_type} • Qs: {t.num_questions} • v{t.version || 1}</p>
                                                    </div>
                                                    <div className="flex gap-2">
                                                        {t.is_published ? (
                                                            <Button size="sm" variant="outline" onClick={() => runTestAction('unpublish', Number(t.id))}>Unpublish</Button>
                                                        ) : (
                                                            <Button size="sm" onClick={() => runTestAction('publish', Number(t.id))}>Publish</Button>
                                                        )}
                                                        <Button size="sm" variant="outline" onClick={() => runTestAction('duplicate', Number(t.id))}>Duplicate</Button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </div>
                    )}

                    {activeTab === 'textbooks' && (
                        <div className="space-y-4">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Textbook Management</CardTitle>
                                    <CardDescription>Book CRUD, chunk explorer, diagnostics, and manual reference mapping.</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                    <div className="grid md:grid-cols-2 gap-2">
                                        <Input placeholder="Book name" value={bookForm.name} onChange={(e) => setBookForm({ ...bookForm, name: e.target.value })} />
                                        <Input placeholder="Author" value={bookForm.author} onChange={(e) => setBookForm({ ...bookForm, author: e.target.value })} />
                                        <Input placeholder="Edition" value={bookForm.edition} onChange={(e) => setBookForm({ ...bookForm, edition: e.target.value })} />
                                        <select className="h-10 rounded-md border bg-background px-3 text-sm" value={bookForm.subject} onChange={(e) => setBookForm({ ...bookForm, subject: e.target.value })}>
                                            <option value="">Select subject</option>
                                            {questionSubjects.map((s: any) => (
                                                <option key={s.id} value={s.id}>{s.name}</option>
                                            ))}
                                        </select>
                                        <Input placeholder="Description" value={bookForm.description} onChange={(e) => setBookForm({ ...bookForm, description: e.target.value })} />
                                        <Button onClick={handleCreateBook}>Create Book</Button>
                                    </div>
                                    {adminBooksLoading ? (
                                        <p className="text-sm text-muted-foreground">Loading books...</p>
                                    ) : (
                                        <div className="max-h-36 overflow-auto space-y-1">
                                            {adminBooks.map((b: any) => (
                                                <div key={b.id} className="text-xs rounded-md border p-2 bg-background">#{b.id} {b.name} • {b.author}</div>
                                            ))}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle>Chunk Explorer and Governance</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                    <div className="flex gap-2 flex-wrap">
                                        <Input placeholder="Chunk search" value={chunkQuery} onChange={(e) => setChunkQuery(e.target.value)} />
                                        <Input type="number" placeholder="Page" value={chunkPageFilter} onChange={(e) => setChunkPageFilter(e.target.value)} />
                                        <Button size="sm" variant="outline" onClick={fetchChunks}>Filter</Button>
                                        <Button size="sm" variant="outline" onClick={fetchChunkDiagnostics}>Refresh Diagnostics</Button>
                                    </div>
                                    {chunkDiagnostics && (
                                        <div className="text-xs rounded-md border p-2 bg-muted/20">
                                            Total: {chunkDiagnostics.total_chunks || 0} • Approved: {chunkDiagnostics.approved_chunks || 0} • Rejected: {chunkDiagnostics.rejected_chunks || 0} • Avg quality: {chunkDiagnostics.avg_quality_score || 0}
                                        </div>
                                    )}
                                    <div className="flex gap-2">
                                        <Button size="sm" variant="outline" disabled={selectedChunkIds.length < 2} onClick={() => runChunkAction('merge')}>Merge Selected</Button>
                                        <Button size="sm" variant="outline" disabled={selectedChunkIds.length === 0} onClick={() => runChunkAction('rechunk')}>Re-chunk Selected</Button>
                                        <Badge variant="outline">Selected: {selectedChunkIds.length}</Badge>
                                    </div>
                                    {chunksLoading ? (
                                        <p className="text-sm text-muted-foreground">Loading chunks...</p>
                                    ) : chunks.length === 0 ? (
                                        <p className="text-sm text-muted-foreground">No chunks found.</p>
                                    ) : (
                                        <div className="max-h-52 overflow-auto space-y-1">
                                            {chunks.map((chunk: any) => (
                                                <div key={chunk.id} className="rounded-md border p-2 text-xs bg-background space-y-1">
                                                    <label className="flex items-center gap-2">
                                                        <input type="checkbox" checked={selectedChunkIds.includes(Number(chunk.id))} onChange={() => toggleChunkSelection(Number(chunk.id))} />
                                                        <span>#{chunk.id} {chunk.book_name} p{chunk.page_number} • q={chunk.quality_score}</span>
                                                    </label>
                                                    <p className="line-clamp-2 text-muted-foreground">{chunk.chunk_text}</p>
                                                    <div className="flex gap-2 flex-wrap">
                                                        <Button size="sm" variant="outline" onClick={() => handleChunkMark(Number(chunk.id), 'approved')}>Approve</Button>
                                                        <Button size="sm" variant="outline" onClick={() => handleChunkMark(Number(chunk.id), 'rejected')}>Reject</Button>
                                                        <Button size="sm" variant="outline" onClick={() => runChunkAction('delete', Number(chunk.id))}>Delete</Button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle>Manual Question Reference Mapping</CardTitle>
                                    <CardDescription>Override AI reference mapping with trusted book/page/screenshot data.</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                    <div className="grid md:grid-cols-2 gap-2">
                                        <Input type="number" placeholder="Question ID" value={referenceMapForm.question_id} onChange={(e) => setReferenceMapForm({ ...referenceMapForm, question_id: e.target.value })} />
                                        <select className="h-10 rounded-md border bg-background px-3 text-sm" value={referenceMapForm.textbook_id} onChange={(e) => setReferenceMapForm({ ...referenceMapForm, textbook_id: e.target.value })}>
                                            <option value="">Select textbook (optional)</option>
                                            {adminBooks.map((b: any) => (
                                                <option key={b.id} value={b.id}>{b.name}</option>
                                            ))}
                                        </select>
                                        <Input placeholder="Chapter" value={referenceMapForm.chapter} onChange={(e) => setReferenceMapForm({ ...referenceMapForm, chapter: e.target.value })} />
                                        <Input placeholder="Page number" value={referenceMapForm.page_number} onChange={(e) => setReferenceMapForm({ ...referenceMapForm, page_number: e.target.value })} />
                                    </div>
                                    <textarea className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-20 resize-y" placeholder="Reference excerpt" value={referenceMapForm.excerpt} onChange={(e) => setReferenceMapForm({ ...referenceMapForm, excerpt: e.target.value })} />
                                    <Input type="file" accept="image/*" onChange={(e) => setReferenceScreenshot(e.target.files?.[0] || null)} />
                                    <Button onClick={handleSaveReferenceMap}>Save Reference Override</Button>
                                    <div className="max-h-36 overflow-auto space-y-1">
                                        {referenceOverrides.map((r: any) => (
                                            <div key={r.id} className="text-xs rounded-md border p-2 bg-background">
                                                Q#{r.question} {'->'} {r.textbook_name || 'Manual'} p{r.page_number} {r.chapter ? `• ${r.chapter}` : ''}
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    )}

                    {activeTab === 'analytics' && (
                        <div className="space-y-4">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Weak-Area Intelligence Control</CardTitle>
                                    <CardDescription>Most wrong questions, difficult topics, student/cohort weaknesses, and impact priorities.</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                    <div className="flex gap-2 items-center">
                                        <Input type="number" placeholder="Optional user ID for student weak-area panel" value={weakAreaUserId} onChange={(e) => setWeakAreaUserId(e.target.value)} />
                                        <Button onClick={fetchWeakAreaControl} disabled={weakAreaLoading}>{weakAreaLoading ? 'Loading...' : 'Refresh'}</Button>
                                    </div>
                                    {!weakAreaData ? (
                                        <p className="text-sm text-muted-foreground">No weak-area data loaded yet.</p>
                                    ) : (
                                        <div className="grid xl:grid-cols-2 gap-3">
                                            <div className="rounded-md border p-3 bg-background">
                                                <p className="text-xs font-medium text-muted-foreground mb-2">Most Wrong Questions</p>
                                                <div className="space-y-1 max-h-52 overflow-auto">
                                                    {(weakAreaData.most_wrong_questions || []).map((q: any) => (
                                                        <div key={q.id} className="text-xs rounded border p-2">
                                                            <p className="line-clamp-2">Q#{q.id} • {q.subject__name || '—'} • Reports: {q.wrong_reports}</p>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                            <div className="rounded-md border p-3 bg-background">
                                                <p className="text-xs font-medium text-muted-foreground mb-2">Most Difficult Topics</p>
                                                <div className="space-y-1 max-h-52 overflow-auto">
                                                    {(weakAreaData.most_difficult_topics || []).map((t: any, idx: number) => (
                                                        <div key={idx} className="text-xs rounded border p-2">
                                                            {t.topic__name || '—'} ({t.subject__name || '—'}) • Accuracy: {Number(t.avg_accuracy || 0).toFixed(1)}%
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                            <div className="rounded-md border p-3 bg-background">
                                                <p className="text-xs font-medium text-muted-foreground mb-2">Cohort Weak Areas</p>
                                                <div className="space-y-1 max-h-52 overflow-auto">
                                                    {(weakAreaData.cohort_weak_areas || []).map((t: any, idx: number) => (
                                                        <div key={idx} className="text-xs rounded border p-2">
                                                            {t.topic__name || '—'} • Attempts: {t.total_attempts || 0} • Accuracy: {Number(t.accuracy || 0).toFixed(1)}%
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                            <div className="rounded-md border p-3 bg-background">
                                                <p className="text-xs font-medium text-muted-foreground mb-2">Impact Prioritization</p>
                                                <div className="space-y-1 max-h-52 overflow-auto">
                                                    {(weakAreaData.impact_priorities || []).map((q: any) => (
                                                        <div key={q.id} className="text-xs rounded border p-2">
                                                            Q#{q.id} • Impact: {Number(q.impact_score || 0).toFixed(1)} • Reports: {q.reports || 0} • Attempts: {q.attempts || 0}
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </div>
                    )}

                    {activeTab === 'moderation' && (
                        <Card>
                            <CardHeader>
                                <CardTitle>Unified Issue Queue</CardTitle>
                                <CardDescription>Sort by most reported, most attempted, or highest impact.</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="grid md:grid-cols-4 gap-2">
                                    <select className="h-10 rounded-md border bg-background px-3 text-sm" value={issueSort} onChange={(e) => setIssueSort(e.target.value as 'most_reported' | 'most_attempted' | 'highest_impact')}>
                                        <option value="most_reported">Most Reported</option>
                                        <option value="most_attempted">Most Attempted</option>
                                        <option value="highest_impact">Highest Impact</option>
                                    </select>
                                    <select className="h-10 rounded-md border bg-background px-3 text-sm" value={issueStatusFilter} onChange={(e) => setIssueStatusFilter(e.target.value)}>
                                        <option value="">All statuses</option>
                                        <option value="new">New</option>
                                        <option value="in_progress">In Progress</option>
                                        <option value="resolved">Resolved</option>
                                    </select>
                                    <Button onClick={fetchIssueQueue} disabled={issueQueueLoading}>{issueQueueLoading ? 'Loading...' : 'Refresh Queue'}</Button>
                                </div>
                                {issueQueue.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">No issue rows found for current filters.</p>
                                ) : (
                                    <div className="space-y-2 max-h-130 overflow-auto">
                                        {issueQueue.map((row: any) => (
                                            <div key={row.question_id} className="rounded-md border p-3 bg-background text-sm">
                                                <p className="font-medium">Q#{row.question_id} • {row.question__subject__name || 'Unknown Subject'}</p>
                                                <p className="text-xs text-muted-foreground line-clamp-2 mt-1">{row.question__question_text}</p>
                                                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                                                    <Badge variant="outline">Reports: {row.reports || 0}</Badge>
                                                    <Badge variant="outline">Attempts: {row.attempts || 0}</Badge>
                                                    <Badge variant="outline">Accuracy: {Number(row.accuracy || 0).toFixed(1)}%</Badge>
                                                    <Badge variant="outline">Impact: {Number(row.impact_score || 0).toFixed(1)}</Badge>
                                                    <Badge variant="outline">Status: {row.status || 'new'}</Badge>
                                                </div>
                                                <div className="mt-2 flex flex-wrap gap-2">
                                                    <Button size="sm" variant="outline" onClick={() => handleIssueStatusUpdate(Number(row.question_id), Number(row.feedback_id), 'new')}>Mark New</Button>
                                                    <Button size="sm" variant="outline" onClick={() => handleIssueStatusUpdate(Number(row.question_id), Number(row.feedback_id), 'in_progress')}>Mark In Progress</Button>
                                                    <Button size="sm" variant="outline" onClick={() => handleIssueStatusUpdate(Number(row.question_id), Number(row.feedback_id), 'resolved')}>Mark Resolved</Button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}

                    {activeTab === 'broadcast' && (
                        <div className="space-y-4">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Campaign Composer</CardTitle>
                                    <CardDescription>Create revision campaigns with image URL, deep link, targeting, and schedule.</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                    <div className="grid md:grid-cols-2 gap-2">
                                        <Input placeholder="Campaign title" value={campaignForm.title} onChange={(e) => setCampaignForm({ ...campaignForm, title: e.target.value })} />
                                        <Input type="datetime-local" value={campaignForm.scheduled_for} onChange={(e) => setCampaignForm({ ...campaignForm, scheduled_for: e.target.value })} />
                                        <Input placeholder="Image URL" value={campaignForm.image_url} onChange={(e) => setCampaignForm({ ...campaignForm, image_url: e.target.value })} />
                                        <Input placeholder="Deep link (e.g. /questions?topic=...)" value={campaignForm.deep_link} onChange={(e) => setCampaignForm({ ...campaignForm, deep_link: e.target.value })} />
                                        <select className="h-10 rounded-md border bg-background px-3 text-sm" value={campaignForm.role} onChange={(e) => setCampaignForm({ ...campaignForm, role: e.target.value })}>
                                            <option value="all">Audience: All</option>
                                            <option value="student">Audience: Students</option>
                                            <option value="admin">Audience: Admins</option>
                                        </select>
                                        <label className="flex items-center gap-2 text-sm">
                                            <input type="checkbox" checked={campaignForm.active_only} onChange={(e) => setCampaignForm({ ...campaignForm, active_only: e.target.checked })} />
                                            Active users only
                                        </label>
                                    </div>
                                    <textarea className="w-full rounded-md border bg-background px-3 py-2 text-sm min-h-20 resize-y" placeholder="Campaign message" value={campaignForm.message} onChange={(e) => setCampaignForm({ ...campaignForm, message: e.target.value })} />
                                    <Button onClick={handleCreateCampaign} disabled={campaignSaving}>{campaignSaving ? 'Saving...' : 'Save Campaign'}</Button>
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <div className="flex items-center justify-between">
                                        <CardTitle>Campaign Delivery Status</CardTitle>
                                        <Button size="sm" variant="outline" onClick={fetchCampaigns} disabled={campaignsLoading}>{campaignsLoading ? 'Loading...' : 'Refresh'}</Button>
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    {campaigns.length === 0 ? (
                                        <p className="text-sm text-muted-foreground">No campaigns found.</p>
                                    ) : (
                                        <div className="space-y-2 max-h-115 overflow-auto">
                                            {campaigns.map((row: any) => (
                                                <div key={row.id} className="rounded-md border p-3 bg-background text-sm">
                                                    <div className="flex items-center justify-between gap-2">
                                                        <p className="font-medium">{row.title}</p>
                                                        <Badge variant="outline">{row.delivery_status || 'draft'}</Badge>
                                                    </div>
                                                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{row.message}</p>
                                                    <p className="text-xs mt-1">Sent: {row.delivery_count || 0} {row.failure_report ? `• Failure: ${row.failure_report}` : ''}</p>
                                                    <div className="mt-2">
                                                        <Button size="sm" variant="outline" onClick={() => handleSendCampaignNow(Number(row.id))}>
                                                            Send Now
                                                        </Button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </div>
                    )}

                    {activeTab === 'security' && (
                        <Card>
                            <CardHeader>
                                <CardTitle>Security Operations</CardTitle>
                                <CardDescription>Upcoming controls: suspicious login flags, session revocation, and policy toggles.</CardDescription>
                            </CardHeader>
                        </Card>
                    )}

                    {activeTab === 'audit' && (
                        <Card>
                            <CardHeader>
                                <div className="flex items-center justify-between">
                                    <CardTitle>Audit Logs Explorer</CardTitle>
                                    <Button size="sm" variant="outline" onClick={fetchAuditLogs} disabled={auditLoading}>{auditLoading ? 'Loading...' : 'Refresh'}</Button>
                                </div>
                                <CardDescription>Operational trace for sensitive admin actions.</CardDescription>
                            </CardHeader>
                            <CardContent>
                                {auditRows.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">No audit entries loaded.</p>
                                ) : (
                                    <div className="space-y-2 max-h-130 overflow-auto">
                                        {auditRows.map((row: any) => (
                                            <div key={row.id} className="rounded-md border p-2 bg-background text-xs">
                                                <p className="font-medium">{row.action} • {row.resource_type}#{row.resource_id || '—'}</p>
                                                <p className="text-muted-foreground">{row.actor_username || 'system'} • {new Date(row.created_at).toLocaleString()}</p>
                                                {row.detail && <p className="mt-1">{row.detail}</p>}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}

                    {activeTab === 'finance' && (
                        <Card>
                            <CardHeader>
                                <CardTitle>Finance & Token Ledger</CardTitle>
                                <CardDescription>Upcoming controls: token ledger timeline, anomalies, and adjustment workflow.</CardDescription>
                            </CardHeader>
                        </Card>
                    )}

                    {activeTab === 'ai' && (
                        <Card>
                            <CardHeader>
                                <CardTitle>Revision History, Diff and Undo</CardTitle>
                                <CardDescription>Trust and change transparency controls for question content lifecycle.</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="flex gap-2">
                                    <Input type="number" placeholder="Question ID" value={selectedRevisionQuestionId} onChange={(e) => setSelectedRevisionQuestionId(e.target.value)} />
                                    <Button onClick={loadRevisionHistory} disabled={revisionLoading}>{revisionLoading ? 'Loading...' : 'Load Revisions'}</Button>
                                </div>
                                {revisionRows.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">No revision snapshots loaded.</p>
                                ) : (
                                    <div className="space-y-2 max-h-65 overflow-auto">
                                        {revisionRows.map((row: any) => (
                                            <div key={row.id} className="rounded-md border p-2 bg-background text-xs">
                                                <p className="font-medium">Revision #{row.id} • {row.changed_by_username || 'system'} • {new Date(row.created_at).toLocaleString()}</p>
                                                <p className="text-muted-foreground">{row.reason || 'No reason provided'}</p>
                                                <div className="mt-2 flex gap-2">
                                                    <Button size="sm" variant="outline" onClick={() => loadRevisionDiff(Number(selectedRevisionQuestionId), Number(row.id))}>View Diff</Button>
                                                    <Button size="sm" variant="outline" onClick={() => handleUndoRevision(Number(selectedRevisionQuestionId), Number(row.id))}>Undo To This</Button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {revisionDiff.length > 0 && (
                                    <div className="rounded-md border p-3 bg-background">
                                        <p className="text-xs font-medium text-muted-foreground mb-2">Revision Diff</p>
                                        <div className="space-y-1 max-h-64 overflow-auto">
                                            {revisionDiff.map((row: any, idx: number) => (
                                                <div key={idx} className="text-xs rounded border p-2">
                                                    <p className="font-medium">{row.field}</p>
                                                    <p className="text-muted-foreground">Before: {String(row.before ?? 'null').slice(0, 200)}</p>
                                                    <p>After: {String(row.after ?? 'null').slice(0, 200)}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}
                </main>
            </div>
        </div>
    );
}
