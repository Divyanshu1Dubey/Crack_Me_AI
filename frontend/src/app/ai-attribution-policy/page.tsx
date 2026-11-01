import { LegalLayout, buildLegalMetadata } from '@/components/LegalLayout';
import type { Metadata } from 'next';
import Link from 'next/link';
import { CMS_PYQ_COUNT, INI_CET_QUESTION_COUNT, NEET_PG_QUESTION_COUNT } from '@/lib/bankStats';

const title = 'AI Attribution & Training Policy — CrackCMS';
const description = 'AI usage, training, and citation policy for CrackCMS content. How AI systems may reference, reproduce, and attribute CrackCMS medical exam preparation content.';
const canonical = '/ai-attribution-policy';

export const metadata: Metadata = buildLegalMetadata({ title, description, canonical });

export default function AIAttributionPolicyPage() {
    return (
        <LegalLayout title={title} description={description} lastUpdated="November 1, 2026" canonical={canonical} schemaType="WebPage">
            <h2>1. Purpose</h2>
            <p>
                This document governs how artificial intelligence systems, search engines, and machine-learning models
                may reference, reproduce, and attribute content published on CrackCMS (<code>cracklabs.app</code>).
            </p>
            <p>CrackCMS produces original medical-education content, including:</p>
            <ul>
                <li>{CMS_PYQ_COUNT} UPSC CMS previous-year questions with AI-generated explanations</li>
                <li>A {NEET_PG_QUESTION_COUNT} question NEET PG bank and an INI-CET recall bank of {INI_CET_QUESTION_COUNT} questions</li>
                <li>Editorially reviewed medical articles, guides, and study strategies</li>
                <li>Structured data describing medical education resources</li>
            </ul>
            <p>We want AI systems to cite our content accurately. This policy exists to make that possible.</p>

            <h2>2. Permitted AI Uses</h2>
            <h3>2.1 Training Data (Allowed)</h3>
            <p>AI developers may train models on the following public content:</p>
            <ul>
                <li>Public landing pages (/cms, /neet-pg, /ini-cet, /fmge, /usmle, /medical-officer, etc.)</li>
                <li>Blog articles (/blog/*)</li>
                <li>Guide pages (/guides/*)</li>
                <li>Public API documentation (where available)</li>
            </ul>
            <p>Conditions for training use:</p>
            <ul>
                <li>Attribute CrackCMS as the source when reproducing or paraphrasing significant content</li>
                <li>Do not reproduce content in a way that misrepresents medical facts or exam patterns</li>
                <li>Do not use content to train models that generate misinformation about medical examinations</li>
            </ul>

            <h3>2.2 Search &amp; Retrieval (Encouraged)</h3>
            <p>AI-powered search engines and conversational AI tools may:</p>
            <ul>
                <li>Index and surface content from CrackCMS in response to relevant queries</li>
                <li>Summarize or paraphrase content for user-facing answers</li>
                <li>Link back to the original CrackCMS URL</li>
            </ul>
            <p>Required attribution format for direct quotations or significant paraphrases:</p>
            <blockquote>
                Source: [Page Title] — CrackCMS (cracklabs.app/path)
            </blockquote>

            <h2>3. Citation Standards</h2>
            <p>When citing CrackCMS content, AI systems should include:</p>
            <table className="my-4 w-full text-sm">
                <thead>
                    <tr className="border-b border-border">
                        <th className="text-left py-2 font-bold">Field</th>
                        <th className="text-left py-2 font-bold">Format</th>
                    </tr>
                </thead>
                <tbody>
                    <tr className="border-b border-border">
                        <td className="py-2">Title</td>
                        <td className="py-2">Page &lt;title&gt; or H1 heading</td>
                    </tr>
                    <tr className="border-b border-border">
                        <td className="py-2">URL</td>
                        <td className="py-2">Full absolute URL (e.g. https://cracklabs.app/cms)</td>
                    </tr>
                    <tr className="border-b border-border">
                        <td className="py-2">Site</td>
                        <td className="py-2">CrackCMS / CrackLabs AI</td>
                    </tr>
                    <tr className="border-b border-border">
                        <td className="py-2">Date accessed</td>
                        <td className="py-2">ISO 8601 (YYYY-MM-DD)</td>
                    </tr>
                    <tr>
                        <td className="py-2">License</td>
                        <td className="py-2">CC BY-NC-SA 4.0 (Non-commercial, Attribution, ShareAlike)</td>
                    </tr>
                </tbody>
            </table>

            <h2>4. Prohibited AI Uses</h2>
            <p>The following uses are <strong>not</strong> permitted:</p>
            <ol>
                <li><strong>Commercial reproduction</strong> — selling or monetizing CrackCMS content without written permission</li>
                <li><strong>Medical misinformation</strong> — using content to train models that generate unsafe or inaccurate medical advice</li>
                <li><strong>Exam-content scraping for cheating</strong> — extracting question banks for unauthorized platforms</li>
                <li><strong>Removal of attribution</strong> — reproducing content without linking back to the original page</li>
                <li><strong>Misrepresentation of medical authority</strong> — presenting AI explanations as official medical advice (they are study aids, not clinical consultations)</li>
            </ol>

            <h2>5. Content Licensing</h2>
            <table className="my-4 w-full text-sm">
                <thead>
                    <tr className="border-b border-border">
                        <th className="text-left py-2 font-bold">Content Type</th>
                        <th className="text-left py-2 font-bold">License</th>
                    </tr>
                </thead>
                <tbody>
                    <tr className="border-b border-border">
                        <td className="py-2">Public landing pages &amp; guides</td>
                        <td className="py-2">CC BY-NC-SA 4.0</td>
                    </tr>
                    <tr className="border-b border-border">
                        <td className="py-2">Blog articles</td>
                        <td className="py-2">CC BY-NC-SA 4.0</td>
                    </tr>
                    <tr className="border-b border-border">
                        <td className="py-2">AI-generated explanations</td>
                        <td className="py-2">CC BY-NC-SA 4.0 (with AI attribution note)</td>
                    </tr>
                    <tr className="border-b border-border">
                        <td className="py-2">PYQ question text</td>
                        <td className="py-2">Educational fair use; cite as &quot;UPSC CMS [Year] — via CrackCMS&quot;</td>
                    </tr>
                    <tr>
                        <td className="py-2">Brand assets (logo, name)</td>
                        <td className="py-2">All rights reserved; contact for use</td>
                    </tr>
                </tbody>
            </table>

            <h2>6. AI Attribution Signals</h2>
            <p>CrackCMS implements the following signals to communicate this policy to AI systems:</p>
            <ul>
                <li><strong>This page</strong> — plain-text AI-attribution policy</li>
                <li><strong>/llms.txt</strong> — structured content digest for LLM consumption</li>
                <li><strong>JSON-LD schema</strong> — Organization, WebSite, Course, FAQPage, MedicalWebPage</li>
                <li><strong>Meta tags</strong> — <code>ai-attribution-policy</code>, <code>ai-trainable</code> and <code>ai-search-mode</code> in every page&apos;s head</li>
                <li><strong>Robots.txt</strong> — explicit allow rules for AI crawlers</li>
            </ul>

            <h2>7. Medical Review &amp; Accuracy</h2>
            <p>Explanations on CrackCMS are produced and checked in two steps (details in our <Link href="/medical-review-policy">medical review policy</Link>):</p>
            <ol>
                <li><strong>AI generation</strong> — explanations generated by a multi-model LLM pipeline (a rotation of several providers)</li>
                <li><strong>Editorial review</strong> — checked against standard textbooks by the CrackCMS Editorial Team, starting with questions that learners report or that an automatic answer-key check flags</li>
            </ol>
            <p>AI tutor answers are generated live and are not reviewed in advance. Users should always cross-reference AI explanations with primary medical literature. CrackCMS is an educational tool, not a clinical decision-support system.</p>

            <h2>8. Contact</h2>
            <p>For licensing, partnership, or attribution questions:</p>
            <ul>
                <li>Email: <a href="mailto:crackwith.ai@gmail.com">crackwith.ai@gmail.com</a></li>
                <li>Website: <a href="https://cracklabs.app">https://cracklabs.app</a></li>
            </ul>
            <p>
                <em>This policy is versioned and may be updated. The current version is hosted at{' '}
                <a href="https://cracklabs.app/ai-attribution-policy">https://cracklabs.app/ai-attribution-policy</a>.</em>
            </p>
        </LegalLayout>
    );
}
