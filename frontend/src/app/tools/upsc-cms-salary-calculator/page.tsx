import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import SalaryCalculator from './SalaryCalculator';

const title = 'UPSC CMS Salary Calculator 2026 — In-Hand Pay, NPA, Promotion';
const description = 'Calculate your in-hand salary as a UPSC CMS Medical Officer. Interactive salary calculator with pay level, NPA, HRA, DA, and promotion growth from MO to CMO to DGHS.';
const slug = 'upsc-cms-salary-calculator';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'What is the salary of a UPSC CMS Medical Officer?', acceptedAnswer: { '@type': 'Answer', text: 'UPSC CMS Medical Officers are paid as per 7th CPC Pay Level 10 (₹56,100 - ₹1,77,500 basic pay) plus 20% Non-Practising Allowance (NPA), HRA (8-24% depending on city), DA (currently 46% of basic), and other allowances. In-hand salary typically ranges ₹80,000 - ₹1,20,000 per month in metro cities.' } },
        { '@type': 'Question', name: 'What is NPA in UPSC CMS?', acceptedAnswer: { '@type': 'Answer', text: 'NPA (Non-Practising Allowance) is 20% of basic pay for Medical Officers who do not engage in private practice. For a Pay Level 10 officer with basic ₹56,100, NPA = ₹11,220 per month.' } },
        { '@type': 'Question', name: 'What is the promotion hierarchy for UPSC CMS officers?', acceptedAnswer: { '@type': 'Answer', text: 'Typical promotion: Medical Officer (MO) → Senior Medical Officer (SMO) → Chief Medical Officer (CMO) → Additional Director General of Health Services (ADGHS) → Director General of Health Services (DGHS). Promotions happen every 4-6 years based on seniority and performance.' } },
    ],
};

export default function UPSCCMSSalaryCalculatorPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'Salary Calculator', path: '/tools/upsc-cms-salary-calculator' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        UPSC CMS Salary Calculator 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Estimate your in-hand monthly and annual salary as a UPSC CMS Medical Officer.
                        Includes basic pay, NPA, HRA, DA, and transport allowance based on 7th CPC.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <SalaryCalculator />

                    <h2 className="text-2xl font-bold mt-12 mb-4">UPSC CMS Salary Structure 2026</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">Pay Matrix (7th CPC)</h3>
                            <p>UPSC CMS Medical Officers are placed in Pay Level 10 as per the 7th Central Pay Commission. The basic pay ranges from ₹56,100 (joining) to ₹1,77,500 (maximum for Level 10).</p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Allowances</h3>
                            <ul className="mt-2 space-y-1 list-disc pl-5">
                                <li><strong>NPA (Non-Practising Allowance):</strong> 20% of basic pay for officers not engaged in private practice.</li>
                                <li><strong>HRA (House Rent Allowance):</strong> 24% for metro cities (X), 16% for tier-2 (Y), 8% for tier-3 (Z).</li>
                                <li><strong>DA (Dearness Allowance):</strong> Currently 46% of basic pay (revised every 6 months).</li>
                                <li><strong>Transport Allowance:</strong> ₹3,600 + DA (for metro: ₹7,200 + DA).</li>
                                <li><strong>Medical Allowance:</strong> ₹500 per month.</li>
                            </ul>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Promotion Hierarchy</h3>
                            <ul className="mt-2 space-y-1 list-disc pl-5">
                                <li><strong>Medical Officer (MO):</strong> Pay Level 10, ₹56,100 - ₹1,77,500</li>
                                <li><strong>Senior Medical Officer (SMO):</strong> Pay Level 11, ₹67,700 - ₹2,08,700</li>
                                <li><strong>Chief Medical Officer (CMO):</strong> Pay Level 12, ₹78,800 - ₹2,09,200</li>
                                <li><strong>Deputy Director / ADGHS:</strong> Pay Level 13-14, ₹1,23,100 - ₹2,15,900</li>
                                <li><strong>Director General of Health Services (DGHS):</strong> Pay Level 17, ₹2,25,000+</li>
                            </ul>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'What is the salary of a UPSC CMS Medical Officer?', a: 'UPSC CMS Medical Officers are paid as per 7th CPC Pay Level 10 (₹56,100 - ₹1,77,500 basic pay) plus 20% NPA, HRA (8-24% depending on city), DA (currently 46%), transport allowance, and medical allowance. In-hand salary typically ranges ₹80,000 - ₹1,20,000 per month in metro cities.' },
                            { q: 'What is NPA in UPSC CMS?', a: 'NPA (Non-Practising Allowance) is 20% of basic pay for Medical Officers who do not engage in private practice. For a Pay Level 10 officer with basic ₹56,100, NPA amounts to ₹11,220 per month.' },
                            { q: 'What is the promotion hierarchy for UPSC CMS officers?', a: 'Typical promotion: Medical Officer → Senior Medical Officer → Chief Medical Officer → Additional Director General of Health Services → Director General of Health Services. Promotions happen every 4-6 years based on seniority and performance.' },
                            { q: 'What is the highest post in UPSC CMS?', a: 'The highest post is Director General of Health Services (DGHS), a Secretary-level position in the Ministry of Health. DGHS heads the entire central health services and advises the government on public health policy.' },
                        ].map((faq) => (
                            <div key={faq.q} className="rounded-xl border border-border bg-card p-5">
                                <h3 className="font-bold text-sm">{faq.q}</h3>
                                <p className="mt-2 text-sm text-muted-foreground">{faq.a}</p>
                            </div>
                        ))}
                    </div>
                </section>
            </div>
        </>
    );
}
