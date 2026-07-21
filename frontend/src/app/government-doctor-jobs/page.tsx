import { ExamLandingLayout, buildExamMetadata, type ExamLandingContent } from '@/components/ExamLandingLayout';

const content: ExamLandingContent = {
    slug: 'government-doctor-jobs',
    name: 'Government Doctor Jobs',
    fullName: 'Central & State Government MBBS Doctor Posts',
    title: 'Government Doctor Jobs 2026 — Medical Officer, Specialist, GDMO Posts | CrackCMS',
    description: 'Latest 2026 government doctor jobs guide for MBBS — UPSC CMS, state PSCs, AIIMS, ESIC, Railways & Defence. Salary, eligibility, and PYQs.',
    tagline: 'Find every central and state government MBBS doctor vacancy in one place — UPSC CMS, AIIMS, PSCs, NHM, ESIC, Defence, Railways.',
    heroBullets: [
        'Every central & state MBBS doctor post in one searchable catalog',
        'Live application deadlines, eligibility, and salary breakdowns',
        'PYQ preparation tailored to each recruitment body',
        'AI tutor that explains selection-pattern differences',
    ],
    stats: [
        { number: '500+', label: 'Active vacancies' },
        { number: '28 states', label: 'Coverage' },
        { number: '₹56k-2L', label: 'Salary range' },
        { number: 'Weekly', label: 'Updates' },
    ],
    pattern: [
        { label: 'UPSC CMS', value: '240 MCQs, 2 papers, -0.33 negative marking' },
        { label: 'State PSC MO', value: '100-200 MCQs, 60-120 min, varies by state' },
        { label: 'AIIMS / PGIMER MO', value: 'CBT 100 MCQs, 90 min' },
        { label: 'ESIC IMO Gr-II', value: 'CBT 100 MCQs, 60 min' },
        { label: 'RRB Medical Practitioner', value: 'CBT, varies by RRB zone' },
    ],
    eligibility: [
        { label: 'MBBS', value: 'From an NMC-recognised college' },
        { label: 'Internship', value: 'Completed (for most posts)' },
        { label: 'Registration', value: 'Permanent or provisional NMC / State Medical Council' },
        { label: 'Age', value: '21-40 years (relaxation as per category)' },
        { label: 'Domicile', value: 'Required for some state posts' },
    ],
    syllabus: [
        { subject: 'General Medicine', weight: '~25%', topics: 'Cardiology, Respiratory, GI, Infectious, Endocrinology' },
        { subject: 'General Surgery', weight: '~15%', topics: 'Common surgical conditions, Trauma, Oncology basics' },
        { subject: 'Paediatrics', weight: '~10%', topics: 'Neonatology, Immunisation, Common infections' },
        { subject: 'OBG', weight: '~10%', topics: 'Antenatal care, High-risk pregnancy, Contraception' },
        { subject: 'PSM / Community Medicine', weight: '~20%', topics: 'Epidemiology, NHM programmes, Biostatistics' },
        { subject: 'Pre-clinical subjects', weight: '~10%', topics: 'Anatomy, Physiology, Biochemistry basics' },
        { subject: 'GK / Reasoning (state PSCs)', weight: '~10%', topics: 'Current affairs, Polity, History, Geography' },
    ],
    books: [
        { name: 'Harrison + Park + Ghai', author: 'Standard authors', why: 'Core MBBS textbooks.' },
        { name: 'Review of PSM (Vivek Jain)', author: 'Vivek Jain', why: 'Highest-yield PSM book.' },
        { name: 'State PSC solved papers', author: 'Various', why: 'Pattern-specific practice.' },
        { name: 'Lucent\'s GK', author: 'Lucent', why: 'For GK portion of state PSCs.' },
    ],
    faqs: [
        { q: 'What are the best government doctor jobs after MBBS?', a: 'Top picks: UPSC CMS (highest pay & prestige), AIIMS/PGIMER MO, ESIC IMO, state PSC Medical Officer, NHM Medical Officer, and Defence Medical Corps.' },
        { q: 'What is the salary of a government doctor?', a: 'Entry-level Medical Officers earn ₹56,100-₹1,77,500 (Pay Level 10) plus NPA 20%, rural allowance, and HRA. Specialists earn up to Pay Level 11 (₹67,700-2,08,700).' },
        { q: 'How to apply for government doctor jobs?', a: 'Apply via UPSC (for CMS), state PSCs, AIIMS/PGIMER portals, ESIC recruitment portal, NHM state websites, or Railway Recruitment Board (RRB) portals.' },
        { q: 'Which government doctor job has the easiest exam?', a: 'NHM and ESIC recruitments typically have shorter, more predictable papers. State PSC MO posts add GK which makes them more competitive.' },
        { q: 'Does CrackCMS track live government doctor vacancies?', a: 'Yes — our /jobs page is updated weekly with central and state MBBS doctor vacancies, including application deadlines and direct apply links.' },
    ],
    accentFrom: 'from-slate-700',
    accentTo: 'to-zinc-900',
    emoji: '🏛️',
    pyqCount: '500+',
};

export const metadata = buildExamMetadata(content);

export default function GovDoctorJobsPage() {
    return ExamLandingLayout(content);
}
