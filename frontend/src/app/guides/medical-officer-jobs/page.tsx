import { GuideLayout, buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';

const title = 'Government Medical Officer Jobs After MBBS — Salary, Posts, Eligibility';
const description = 'Every central & state MBBS doctor post — UPSC CMS, AIIMS MO, state PSCs, NHM, ESIC, Railways, Defence. Salary breakdowns (₹56k-1.2L/month), eligibility, and how to apply.';
const slug = 'medical-officer-jobs';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const faqs = [
    { q: 'What is the highest-paying government doctor job after MBBS?', a: 'Specialist posts in AIIMS, ESIC, and Defence pay the most — Pay Level 11 (₹67,700-2,08,700) plus NPA. General Duty Medical Officers (GDMOs) start at Pay Level 10 (₹56,100-1,77,500).' },
    { q: 'Can final-year MBBS students apply for government doctor jobs?', a: 'For most central posts (UPSC CMS, AIIMS), final-year MBBS students can apply provisionally, but the MBBS degree must be completed before document verification. State PSCs typically require a completed MBBS.' },
    { q: 'How to apply for UPSC CMS?', a: 'Apply online at upsc.gov.in during the application window (typically April-May). The exam is in July. UPSC CMS is considered the most prestigious MO recruitment.' },
];

export default function MedicalOfficerJobsGuide() {
    return (
        <GuideLayout
            title={title}
            description={description}
            slug={slug}
            heading="Government Medical Officer Jobs After MBBS"
            lede="Every central and state MBBS doctor post in one place — UPSC CMS, AIIMS, PGIMER, state PSCs, NHM, ESIC, Railways, Defence. Salary breakdowns, eligibility, and how to apply."
            author="Dr. CrackCMS Editorial Team"
            lastUpdated="July 21, 2026"
            readingTime="8 min"
            faqs={faqs}
        >
            <h2>Why pursue a government doctor job?</h2>
            <ul>
                <li><strong>Job security:</strong> Permanent positions with pension benefits (under NPS).</li>
                <li><strong>Work-life balance:</strong> Predictable hours, weekends off, fixed duty rosters.</li>
                <li><strong>Pay &amp; perks:</strong> Pay Level 10-13, NPA 20%, HRA, rural allowance, study leave.</li>
                <li><strong>Social impact:</strong> Serve the underserved population through public health programmes.</li>
                <li><strong>Postgraduate quota:</strong> In-service reservation in PG seats for state government doctors.</li>
            </ul>

            <h2>Central Government MBBS Doctor Posts</h2>

            <h3>UPSC CMS — Combined Medical Services</h3>
            <ul>
                <li><strong>Posts:</strong> GDMO (Central Health Service), ADMO (Railways), MO (MCD), Junior Scale (defence)</li>
                <li><strong>Salary:</strong> Pay Level 10 (₹56,100 - ₹1,77,500) + 20% NPA + HRA</li>
                <li><strong>Exam:</strong> 240 MCQs (2 papers), -0.33 negative marking, offline</li>
                <li><strong>Apply:</strong> upsc.gov.in (April notification, July exam)</li>
                <li><strong>Vacancies:</strong> 800-1,200 per year</li>
            </ul>

            <h3>AIIMS Medical Officer</h3>
            <ul>
                <li><strong>Posts:</strong> MO, Senior MO, Specialist Gr-II</li>
                <li><strong>Salary:</strong> Pay Level 10 (₹56,100 - ₹1,77,500) + NPA</li>
                <li><strong>Exam:</strong> CBT 100 MCQs, 90 min</li>
                <li><strong>Apply:</strong> aiimsexams.ac.in</li>
                <li><strong>Vacancies:</strong> 100-300 per AIIMS per recruitment</li>
            </ul>

            <h3>ESIC (Employees&apos; State Insurance Corporation) — IMO Gr-II</h3>
            <ul>
                <li><strong>Posts:</strong> Insurance Medical Officer Grade II</li>
                <li><strong>Salary:</strong> Pay Level 10 + NPA</li>
                <li><strong>Exam:</strong> CBT 100 MCQs, 60 min</li>
                <li><strong>Apply:</strong> esic.gov.in</li>
                <li><strong>Vacancies:</strong> 1,000+ annually across India</li>
            </ul>

            <h3>NHM (National Health Mission)</h3>
            <ul>
                <li><strong>Posts:</strong> State-level Medical Officer, Specialist MO</li>
                <li><strong>Salary:</strong> ₹60,000 - ₹1,50,000 (consolidated, varies by state)</li>
                <li><strong>Apply:</strong> State NHM websites</li>
                <li><strong>Vacancies:</strong> Thousands across all states</li>
            </ul>

            <h3>Defence Medical Corps / Armed Forces Medical Services</h3>
            <ul>
                <li><strong>Posts:</strong> Captain (entry-level), Major after 4 years</li>
                <li><strong>Salary:</strong> Pay Level 10B (₹61,300 - ₹1,93,900) + Military Service Pay + NPA + perks</li>
                <li><strong>Apply:</strong> amcsscentry.gov.in</li>
                <li><strong>Selection:</strong> NEET-PG based screening + SSB interview</li>
            </ul>

            <h3>Railways (RRB)</h3>
            <ul>
                <li><strong>Posts:</strong> Railway Medical Practitioner (Part-time / General Duty)</li>
                <li><strong>Salary:</strong> Pay Level 10 + NPA + Railway perks</li>
                <li><strong>Apply:</strong> rrbcdg.gov.in (varies by RRB zone)</li>
            </ul>

            <h2>State Government MBBS Doctor Posts</h2>
            <p>
                Every state Public Service Commission (PSC) and state health department recruits Medical Officers.
                Some of the most popular:
            </p>
            <table>
                <thead><tr><th>State</th><th>Recruiter</th><th>Annual vacancies (approx)</th></tr></thead>
                <tbody>
                    <tr><td>Uttar Pradesh</td><td>UPPSC</td><td>2,000+</td></tr>
                    <tr><td>Madhya Pradesh</td><td>MPPSC</td><td>1,500+</td></tr>
                    <tr><td>Rajasthan</td><td>RPSC</td><td>1,000+</td></tr>
                    <tr><td>Bihar</td><td>BPSC</td><td>1,000+</td></tr>
                    <tr><td>Tamil Nadu</td><td>TNPSC / MRB</td><td>2,500+</td></tr>
                    <tr><td>Maharashtra</td><td>MPSC</td><td>1,500+</td></tr>
                    <tr><td>Karnataka</td><td>KPSC</td><td>800+</td></tr>
                    <tr><td>West Bengal</td><td>WBPSC</td><td>1,200+</td></tr>
                    <tr><td>Gujarat</td><td>GPSC</td><td>700+</td></tr>
                    <tr><td>Kerala</td><td>KPSC</td><td>600+</td></tr>
                </tbody>
            </table>

            <h2>Salary breakdown — what you actually take home</h2>
            <p>
                Government doctor salaries vary by post and state. A typical breakdown for a Central GDMO (Pay Level 10):
            </p>
            <ul>
                <li>Basic Pay: ₹56,100 (starting)</li>
                <li>Dearness Allowance (DA): ~50% of basic (revised quarterly) — ₹28,050</li>
                <li>Non-Practising Allowance (NPA): 20% of basic — ₹11,220</li>
                <li>House Rent Allowance (HRA): 8-24% based on city class — ₹4,488 to ₹13,464</li>
                <li>Transport Allowance: ₹3,600 + DA</li>
                <li><strong>Approximate gross in-hand:</strong> ₹1,00,000 - ₹1,20,000 per month</li>
            </ul>

            <h2>How to apply</h2>
            <ol>
                <li><strong>UPSC CMS:</strong> upsc.gov.in — April notification, July exam</li>
                <li><strong>ESIC IMO:</strong> esic.gov.in — rolling recruitments</li>
                <li><strong>AIIMS MO:</strong> aiimsexams.ac.in — periodic recruitment</li>
                <li><strong>State PSCs:</strong> respective state PSC websites — 1-2 cycles per year</li>
                <li><strong>NHM:</strong> state NHM portals — rolling</li>
            </ol>

            <h2>Why CrackCMS?</h2>
            <p>
                CrackCMS covers PYQs for UPSC CMS, ESIC, AIIMS MO, and all major state PSCs. AI tutor explains every
                answer with public-health context, and our analytics identify your weakest topics. Subscribe to
                our <a href="/jobs">/jobs</a> page for weekly vacancy updates.
            </p>
        </GuideLayout>
    );
}
