import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getAllCmsSubjects, getCmsSubject } from '@/lib/subjectHubData';
import SubjectHubLayout, { buildSubjectHubMetadata } from '@/components/SubjectHubLayout';

export async function generateStaticParams() {
    return getAllCmsSubjects().map((slug) => ({ slug }));
}

export async function generateMetadata(
    { params }: { params: Promise<{ slug: string }> },
): Promise<Metadata> {
    const { slug } = await params;
    const data = getCmsSubject(slug);
    if (!data) return { title: 'UPSC CMS Subject | CrackCMS', robots: { index: false } };
    return buildSubjectHubMetadata(data);
}

export const revalidate = 86400; // 24 hours

export default async function CMSSubjectPage({ params }: { params: Promise<{ slug: string }> }) {
    const { slug } = await params;
    const data = getCmsSubject(slug);
    if (!data) notFound();
    return SubjectHubLayout(data);
}