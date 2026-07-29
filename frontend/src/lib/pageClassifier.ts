/**
 * pageClassifier.ts — Derive a stable `page_type` + `page_group` from a
 * pathname so every event can be aggregated into standard GA4 + PostHog
 * dashboards without 100+ individual page reports.
 *
 * Keep this list SHORT and STABLE — adding new types is a breaking change
 * for existing dashboards.
 */

export type PageType =
    | 'home'
    | 'blog_index'
    | 'blog_post'
    | 'blog_category'
    | 'guides_index'
    | 'guide'
    | 'exam_microsite'
    | 'exam_landing'
    | 'exam_pyq_year'
    | 'exam_subject_hub'
    | 'exam_comparison'
    | 'exam_cutoff'
    | 'exam_strategy'
    | 'exam_books'
    | 'question_bank'
    | 'question_practice'
    | 'simulator'
    | 'tests_index'
    | 'test_detail'
    | 'ai_tutor'
    | 'ai_generate'
    | 'ai_roadmap'
    | 'flashcards'
    | 'leaderboard'
    | 'dashboard'
    | 'analytics'
    | 'bookmarks'
    | 'feedback'
    | 'tokens'
    | 'settings'
    | 'subscription'
    | 'subscription_success'
    | 'jobs'
    | 'resources'
    | 'textbooks'
    | 'trends'
    | 'recall_search'
    | 'login'
    | 'register'
    | 'forgot_password'
    | 'reset_password'
    | 'auth_callback'
    | 'admin'
    | 'admin_import'
    | 'admin_ingestion'
    | 'admin_recall'
    | 'admin_questions'
    | 'admin_announcements'
    | 'admin_jobs'
    | 'legal'
    | 'about'
    | 'contact'
    | 'not_found'
    | 'other';

export interface PageClassification {
    page_type: PageType;
    page_group: string;
    exam_slug?: string;
    year?: string;
    subject?: string;
    topic?: string;
    guide_slug?: string;
    comparison_slug?: string;
    strategy_slug?: string;
    book_slug?: string;
    blog_slug?: string;
    blog_category?: string;
    test_id?: string;
}

export function classifyPath(pathname: string): PageClassification {
    const path = pathname || '/';
    const out: PageClassification = { page_type: 'other', page_group: 'misc' };

    if (path === '/' || path === '') {
        return { page_type: 'home', page_group: 'home' };
    }

    // Blog
    if (path === '/blog') {
        return { page_type: 'blog_index', page_group: 'blog' };
    }
    const blogMatch = path.match(/^\/blog\/category\/([^/]+)\/?$/);
    if (blogMatch) {
        return {
            page_type: 'blog_category',
            page_group: 'blog',
            blog_category: blogMatch[1],
        };
    }
    const blogPost = path.match(/^\/blog\/([^/]+)\/?$/);
    if (blogPost) {
        return {
            page_type: 'blog_post',
            page_group: 'blog',
            blog_slug: blogPost[1],
        };
    }

    // Guides
    if (path === '/guides') return { page_type: 'guides_index', page_group: 'guides' };
    const guideMatch = path.match(/^\/guides\/([^/]+)\/?$/);
    if (guideMatch) {
        return {
            page_type: 'guide',
            page_group: 'guides',
            guide_slug: guideMatch[1],
        };
    }

    // Exam microsites (CMS / NEET PG / USMLE etc.)
    const examSlugMatch = path.match(/^\/exams\/([^/]+)\/?$/);
    if (examSlugMatch) {
        return {
            page_type: 'exam_microsite',
            page_group: 'exam_microsite',
            exam_slug: examSlugMatch[1],
        };
    }

    // CMS tree
    if (path === '/cms') {
        return { page_type: 'exam_landing', page_group: 'cms', exam_slug: 'cms' };
    }
    const cmsPyqYear = path.match(/^\/cms\/pyq\/(\d{4})\/?$/);
    if (cmsPyqYear) {
        return {
            page_type: 'exam_pyq_year',
            page_group: 'cms',
            exam_slug: 'cms',
            year: cmsPyqYear[1],
        };
    }
    if (path === '/cms/pyq') {
        return { page_type: 'exam_landing', page_group: 'cms', exam_slug: 'cms' };
    }
    const cmsSubject = path.match(/^\/cms\/subject\/([^/]+)\/?$/);
    if (cmsSubject) {
        return {
            page_type: 'exam_subject_hub',
            page_group: 'cms',
            exam_slug: 'cms',
            subject: cmsSubject[1],
        };
    }
    if (path === '/cms/subject') {
        return { page_type: 'exam_landing', page_group: 'cms', exam_slug: 'cms' };
    }
    const cmsComparison = path.match(/^\/cms\/vs-([^/]+)\/?$/);
    if (cmsComparison) {
        return {
            page_type: 'exam_comparison',
            page_group: 'cms',
            exam_slug: 'cms',
            comparison_slug: cmsComparison[1],
        };
    }
    if (path === '/cms/cutoff') {
        return { page_type: 'exam_cutoff', page_group: 'cms', exam_slug: 'cms' };
    }
    const cmsCutoff = path.match(/^\/cms\/cutoff\/(\d{4})\/?$/);
    if (cmsCutoff) {
        return {
            page_type: 'exam_cutoff',
            page_group: 'cms',
            exam_slug: 'cms',
            year: cmsCutoff[1],
        };
    }
    if (path === '/cms/strategy') {
        return { page_type: 'exam_strategy', page_group: 'cms', exam_slug: 'cms' };
    }
    const cmsStrategy = path.match(/^\/cms\/strategy\/([^/]+)\/?$/);
    if (cmsStrategy) {
        return {
            page_type: 'exam_strategy',
            page_group: 'cms',
            exam_slug: 'cms',
            strategy_slug: cmsStrategy[1],
        };
    }
    if (path === '/cms/books') {
        return { page_type: 'exam_books', page_group: 'cms', exam_slug: 'cms' };
    }
    const cmsBook = path.match(/^\/cms\/books\/([^/]+)\/?$/);
    if (cmsBook) {
        return {
            page_type: 'exam_books',
            page_group: 'cms',
            exam_slug: 'cms',
            book_slug: cmsBook[1],
        };
    }

    // NEET PG / INI-CET / FMGE / USMLE landing pages
    const examLanding = ['/neet-pg', '/inicet', '/ini-cet', '/fmge', '/usmle', '/medical-officer', '/government-doctor-jobs'];
    if (examLanding.includes(path)) {
        return { page_type: 'exam_landing', page_group: 'exam_landing', exam_slug: path.slice(1) };
    }
    const neetVs = path.match(/^\/(neet-pg|fmge)\/vs-([^/]+)\/?$/);
    if (neetVs) {
        return {
            page_type: 'exam_comparison',
            page_group: 'exam_comparison',
            exam_slug: neetVs[1],
            comparison_slug: neetVs[2],
        };
    }

    // Question bank + practice
    if (path === '/questions') {
        return { page_type: 'question_bank', page_group: 'question_bank' };
    }
    if (path === '/questions/practice') {
        return { page_type: 'question_practice', page_group: 'question_bank' };
    }
    if (path === '/questions/neet-pg/practice' || path === '/questions/inicet/practice') {
        return { page_type: 'question_practice', page_group: 'question_bank' };
    }
    if (path === '/practice') {
        return { page_type: 'question_practice', page_group: 'question_bank' };
    }
    if (path === '/simulator') {
        return { page_type: 'simulator', page_group: 'simulator' };
    }
    if (path === '/tests') {
        return { page_type: 'tests_index', page_group: 'tests' };
    }
    const testDetail = path.match(/^\/tests\/([^/]+)\/?$/);
    if (testDetail) {
        return {
            page_type: 'test_detail',
            page_group: 'tests',
            test_id: testDetail[1],
        };
    }

    // AI features
    if (path === '/ai-tutor') return { page_type: 'ai_tutor', page_group: 'ai' };
    if (path === '/generate') return { page_type: 'ai_generate', page_group: 'ai' };
    if (path === '/roadmap') return { page_type: 'ai_roadmap', page_group: 'ai' };
    if (path === '/flashcards') return { page_type: 'flashcards', page_group: 'study' };
    if (path === '/leaderboard') return { page_type: 'leaderboard', page_group: 'leaderboard' };

    // User account
    if (path === '/dashboard') return { page_type: 'dashboard', page_group: 'account' };
    if (path === '/analytics') return { page_type: 'analytics', page_group: 'account' };
    if (path === '/bookmarks') return { page_type: 'bookmarks', page_group: 'account' };
    if (path === '/feedback') return { page_type: 'feedback', page_group: 'account' };
    if (path === '/tokens') return { page_type: 'tokens', page_group: 'account' };
    if (path === '/settings') return { page_type: 'settings', page_group: 'account' };
    if (path === '/subscription') return { page_type: 'subscription', page_group: 'revenue' };
    if (path.startsWith('/subscription/success'))
        return { page_type: 'subscription_success', page_group: 'revenue' };

    // Jobs / Resources / Textbooks / Trends / Recall
    if (path === '/jobs') return { page_type: 'jobs', page_group: 'jobs' };
    if (path === '/resources') return { page_type: 'resources', page_group: 'content' };
    if (path === '/textbooks') return { page_type: 'textbooks', page_group: 'content' };
    if (path === '/trends') return { page_type: 'trends', page_group: 'content' };
    if (path === '/recall/search')
        return { page_type: 'recall_search', page_group: 'recall' };

    // Auth
    if (path === '/login') return { page_type: 'login', page_group: 'auth' };
    if (path === '/register') return { page_type: 'register', page_group: 'auth' };
    if (path === '/forgot-password')
        return { page_type: 'forgot_password', page_group: 'auth' };
    if (path === '/reset-password')
        return { page_type: 'reset_password', page_group: 'auth' };
    if (path.startsWith('/auth/callback'))
        return { page_type: 'auth_callback', page_group: 'auth' };

    // Admin
    if (path.startsWith('/admin/import-center'))
        return { page_type: 'admin_import', page_group: 'admin' };
    if (path.startsWith('/admin/ingestion'))
        return { page_type: 'admin_ingestion', page_group: 'admin' };
    if (path.startsWith('/admin/recall'))
        return { page_type: 'admin_recall', page_group: 'admin' };
    if (path.startsWith('/admin/questions-editor'))
        return { page_type: 'admin_questions', page_group: 'admin' };
    if (path.startsWith('/admin/announcements'))
        return { page_type: 'admin_announcements', page_group: 'admin' };
    if (path.startsWith('/admin/jobs'))
        return { page_type: 'admin_jobs', page_group: 'admin' };
    if (path.startsWith('/admin')) return { page_type: 'admin', page_group: 'admin' };

    // Legal / static
    const legalPages = [
        '/about',
        '/contact',
        '/terms',
        '/privacy-policy',
        '/cookie-policy',
        '/disclaimer',
        '/editorial-policy',
        '/medical-review-policy',
        '/refund-policy',
    ];
    if (legalPages.includes(path))
        return { page_type: path === '/about' || path === '/contact' ? path.slice(1) as PageType : 'legal', page_group: 'static' };

    return out;
}

export default classifyPath;