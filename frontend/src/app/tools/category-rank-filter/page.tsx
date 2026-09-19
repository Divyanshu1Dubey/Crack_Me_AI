import { buildGuideMetadata } from '@/components/GuideLayout';
import type { Metadata } from 'next';
import { siteName, siteUrl } from '@/lib/seo';
import Breadcrumbs from '@/components/Breadcrumbs';
import CategoryRankFilter from './CategoryRankFilter';

const title = 'CategoryRankFilter 2026 — Compare UPSC CMS Rank Across General, OBC, SC, ST, PwBD';
const description = 'Compare your UPSC CMS rank across reservation categories. See how General, OBC, SC, ST, and PwBD reservation affects cutoffs and selection chances.';
const slug = 'category-rank-filter';

export const metadata: Metadata = buildGuideMetadata({ title, description, slug });

const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: [
        { '@type': 'Question', name: 'How does UPSC CMS reservation affect my rank?', acceptedAnswer: { '@type': 'Answer', text: 'UPSC CMS reservation means candidates are ranked separately within their category (General, OBC, SC, ST, PwBD). A rank of 100 in General is not the same as rank 100 in SC — the SC rank is relative only to SC candidates. The Category Rank Filter tool converts your rank across categories so you can compare selection chances under different reservation pools.' } },
        { '@type': 'Question', name: 'What is the reservation percentage in UPSC CMS?', acceptedAnswer: { '@type': 'Answer', text: 'UPSC CMS reservation: General — open competition; OBC (Non-Creamy Layer) — 27%; SC — 15%; ST — 7.5%; PwBD (Persons with Benchmark Disability) — 4% (horizontal reservation). These percentages are applied to the total vacancies each year.' } },
        { '@type': 'Question', name: 'How is PwBD reservation different in UPSC CMS?', acceptedAnswer: { '@type': 'Answer', text: 'PwBD reservation in UPSC CMS is horizontal — it is filled from within each category (General, OBC, SC, ST), not as a separate pool. This means a PwBD candidate in the General category competes with other General candidates, and the 4% PwBD seats are carved out of that category\'s allocation. The Category Rank Filter accounts for this by treating PwBD as a cross-category filter.' } },
        { '@type': 'Question', name: 'Can I use my General category rank to estimate OBC/SC/ST chances?', acceptedAnswer: { '@type': 'Answer', text: 'Yes, but with caveats. A General category rank can be converted to an equivalent rank in other categories using the Category Rank Filter tool, which accounts for the different applicant pool sizes and reservation percentages. However, actual selection also depends on how many candidates from each category apply, the number of vacancies, and the merit list. Use the tool as an indicative guide only.' } },
        { '@type': 'Question', name: 'What is the difference between category rank and overall rank in UPSC CMS?', acceptedAnswer: { '@type': 'Answer', text: 'Category rank is your position within your specific reservation category (e.g., 50th among OBC candidates). Overall rank is your position among all candidates regardless of category. UPSC CMS uses category ranks for selection under reservation, while overall rank is used for inter-se-merit and tie-breaking. The Category Rank Filter helps you understand how your category rank translates to equivalent positions in other categories.' } },
    ],
};

export default function CategoryRankFilterPage() {
    return (
        <>
            <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
            <div className="min-h-screen bg-background text-foreground">
                <div className="mx-auto max-w-5xl px-4 pt-6 sm:px-6">
                    <Breadcrumbs items={[{ name: 'UPSC CMS', path: '/cms' }, { name: 'CategoryRankFilter', path: '/tools/category-rank-filter' }]} />
                </div>
                <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
                    <h1 className="text-3xl font-black tracking-tight sm:text-4xl md:text-5xl">
                        CategoryRankFilter 2026
                    </h1>
                    <p className="mt-4 max-w-3xl text-lg text-muted-foreground">
                        Compare how your UPSC CMS rank translates across General, OBC, SC, ST, and PwBD
                        categories. See how reservation quotas affect cutoffs and understand your selection
                        chances from every category perspective — all computed client-side.
                    </p>
                </section>

                <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
                    <CategoryRankFilter />

                    <h2 className="text-2xl font-bold mt-12 mb-4">About This Tool</h2>
                    <div className="space-y-6 text-muted-foreground">
                        <div>
                            <h3 className="font-bold text-foreground">How to Use</h3>
                            <ol className="mt-2 space-y-1 list-decimal pl-5">
                                <li>
                                    Enter your category-wise rank (the rank you received in your
                                    reservation category list).
                                </li>
                                <li>
                                    Select your reservation category (General, OBC, SC, ST, or PwBD).
                                </li>
                                <li>
                                    Click <strong>Compare Across Categories</strong> to see equivalent
                                    ranks, estimated vacancies, and selection chances for all categories.
                                </li>
                                <li>
                                    Use the results to understand how a rank in one category maps to
                                    others and where your selection chances are strongest.
                                </li>
                            </ol>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Why This Matters</h3>
                            <p>
                                UPSC CMS uses category-wise merit lists for selection under reservation.
                                A candidate&rsquo;s rank in the General category does not directly compare
                                to their rank in SC or ST, because each category has its own vacancy pool
                                and applicant pool. Understanding how ranks map across categories helps
                                you gauge your real selection chances, plan backup options, and make
                                informed decisions during the counselling or choice-filling process.
                            </p>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">UPSC CMS Reservation Overview</h3>
                            <ul className="mt-2 space-y-1 list-disc pl-5">
                                <li><strong>General:</strong> Open competition — no reservation.</li>
                                <li><strong>OBC (Non-Creamy Layer):</strong> 27% reservation.</li>
                                <li><strong>SC:</strong> 15% reservation.</li>
                                <li><strong>ST:</strong> 7.5% reservation.</li>
                                <li><strong>PwBD:</strong> 4% horizontal reservation (filled from within each category).</li>
                            </ul>
                        </div>
                        <div>
                            <h3 className="font-bold text-foreground">Important Note on PwBD</h3>
                            <p>
                                PwBD reservation is horizontal in UPSC CMS, meaning the 4% seats are
                                filled from within each category&rsquo;s allocation. A PwBD candidate in the
                                General category competes with other General candidates, and the PwBD
                                seat is carved out of that category&rsquo;s quota. The tool reflects this by
                                treating PwBD as a cross-category filter rather than a separate pool.
                            </p>
                        </div>
                    </div>

                    <h2 className="text-2xl font-bold mt-10 mb-4">Frequently Asked Questions</h2>
                    <div className="space-y-4">
                        {[
                            { q: 'How does UPSC CMS reservation affect my rank?', a: 'UPSC CMS reservation means candidates are ranked separately within their category (General, OBC, SC, ST, PwBD). A rank of 100 in General is not the same as rank 100 in SC — the SC rank is relative only to SC candidates. The Category Rank Filter tool converts your rank across categories so you can compare selection chances under different reservation pools.' },
                            { q: 'What is the reservation percentage in UPSC CMS?', a: 'UPSC CMS reservation: General — open competition; OBC (Non-Creamy Layer) — 27%; SC — 15%; ST — 7.5%; PwBD (Persons with Benchmark Disability) — 4% (horizontal reservation). These percentages are applied to the total vacancies each year.' },
                            { q: 'How is PwBD reservation different in UPSC CMS?', a: 'PwBD reservation in UPSC CMS is horizontal — it is filled from within each category (General, OBC, SC, ST), not as a separate pool. This means a PwBD candidate in the General category competes with other General candidates, and the 4% PwBD seats are carved out of that category\'s allocation. The Category Rank Filter accounts for this by treating PwBD as a cross-category filter.' },
                            { q: 'Can I use my General category rank to estimate OBC/SC/ST chances?', a: 'Yes, but with caveats. A General category rank can be converted to an equivalent rank in other categories using the Category Rank Filter tool, which accounts for the different applicant pool sizes and reservation percentages. However, actual selection also depends on how many candidates from each category apply, the number of vacancies, and the merit list. Use the tool as an indicative guide only.' },
                            { q: 'What is the difference between category rank and overall rank in UPSC CMS?', a: 'Category rank is your position within your specific reservation category (e.g., 50th among OBC candidates). Overall rank is your position among all candidates regardless of category. UPSC CMS uses category ranks for selection under reservation, while overall rank is used for inter-se-merit and tie-breaking. The Category Rank Filter helps you understand how your category rank translates to equivalent positions in other categories.' },
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
