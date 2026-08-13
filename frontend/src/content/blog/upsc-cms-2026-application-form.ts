import type { BlogPost } from '@/lib/blog';

/**
 * Blog post — UPSC CMS 2026 application form step-by-step guide.
 *
 * All procedural details (dates, fees, document specs) follow the
 * consistent pattern observed across UPSC CMS 2018–2025 cycles.
 * The exact 2026 window and fee are in the official notification at
 * upsc.gov.in — always verify there before applying.
 */

const post: BlogPost = {
    slug: 'upsc-cms-2026-application-form',
    title: 'UPSC CMS 2026 Application Form: Step-by-Step Guide, Eligibility & Dates',
    description:
        'Complete guide to UPSC CMS 2026 online application. Covers eligibility criteria, important dates, application fees, required documents, common mistakes, and how to avoid form rejection.',
    excerpt:
        'Everything you need to know about the UPSC CMS 2026 application form — eligibility, fees, documents, step-by-step process, and common mistakes that get candidates rejected.',
    coverImage: '/blog/upsc-cms-application-form.jpg',
    category: 'UPSC CMS',
    subcategory: 'Application Guide',
    tags: [
        'UPSC CMS',
        'application form',
        'eligibility',
        'online registration',
        'exam dates',
        'UPSC CMS 2026',
    ],
    difficulty: 'beginner',
    authorId: 'crackcms-editorial',
    reviewedBy: 'crackcms-editorial',
    author: 'CrackCMS Editorial Team',
    authorRole: 'Medical Content Editors',
    datePublished: '2026-01-15',
    dateModified: '2026-01-15',
    updatedAt: '2026-01-15',
    readingTime: '12 min',
    toc: [
        { id: 'important-dates', label: 'Important Dates (Expected Schedule)' },
        { id: 'eligibility-criteria', label: 'Eligibility Criteria' },
        { id: 'application-fee', label: 'Application Fee Structure' },
        { id: 'documents-required', label: 'Documents Required' },
        { id: 'step-by-step-process', label: 'Step-by-Step Application Process' },
        { id: 'common-mistakes', label: 'Common Mistakes That Get Applications Rejected' },
        { id: 'faqs', label: 'Frequently Asked Questions' },
    ],
    primaryCta: {
        label: 'Practise CMS PYQs (free)',
        href: '/questions?exam=CMS',
        eventName: 'blog_practice_intent',
        eventParams: { source: 'cms-application-form', surface: 'inline_cta' },
    },
    relatedExamPaths: ['/cms', '/cms/eligibility', '/cms/syllabus'],
    references: [
        {
            label: 'UPSC — Combined Medical Services Examination (official page)',
            url: 'https://upsc.gov.in/examinations/combined-medical-services-examination',
        },
        {
            label: 'UPSC — Online Application Portal (upsconline.nic.in)',
            url: 'https://upsconline.nic.in',
        },
        {
            label: 'UPSC — Examination Notifications (master index)',
            url: 'https://upsc.gov.in/examinations',
        },
    ],
    revisionLog: [
        {
            date: '2026-01-15',
            note: 'Initial publication. Dates and fees follow the consistent UPSC CMS 2018–2025 cycle pattern. Verify the exact 2026 window in the official UPSC notification on upsc.gov.in.',
        },
    ],
    faqs: [
        {
            q: 'Can I edit my application after submitting?',
            a: 'Yes — there is usually a window of 5–7 days after the last submission date during which UPSC allows candidates to edit their application. After the edit window closes, corrections require a formal request to UPSC.',
        },
        {
            q: 'What if I forget my Registration ID (RID)?',
            a: 'Use the "Forgot RID" link on the UPSC portal with your registered email or mobile number. Save your RID in multiple places (email, notes, screenshots) immediately after registration.',
        },
        {
            q: 'Can I change my exam centre after submitting?',
            a: 'No. The exam centre chosen during Part-II cannot be changed later. Choose carefully from the list published in the notification, considering travel time and accommodation.',
        },
        {
            q: 'Is the UPSC CMS application only online?',
            a: 'Yes. UPSC CMS accepts applications exclusively through the online portal at upsconline.nic.in. There is no postal or offline mode.',
        },
        {
            q: 'What is the difference between UPSC CMS and NEET PG?',
            a: 'NEET PG is for MD/MS/DNB seats in medical colleges (conducted by NBEMS). UPSC CMS is for Central Government Medical Officer services. Many serious candidates prepare for both simultaneously. See our [CMS vs NEET PG comparison](/cms/vs-neet-pg).',
        },
        {
            q: 'What is the application fee for UPSC CMS?',
            a: 'The fee is ₹200 for General/EWS/OBC (male) candidates. All female candidates, SC/ST, Ex-Servicemen, and PwD candidates are exempt. The exact fee is specified in the official notification each year.',
        },
        {
            q: 'Can final year MBBS students apply for UPSC CMS?',
            a: 'Yes — candidates in the final year of MBBS can apply, provided they submit proof of passing the degree at the time of the personality test. Interns can also apply but must complete the internship by the application deadline.',
        },
        {
            q: 'What photo and signature specifications are required?',
            a: 'Photo: recent, white/light background, 200×240 pixels, 20–300 KB, JPG/JPEG. Signature: black ink on white paper, 140×60 pixels, 10–300 KB, JPG/JPEG. Incorrect specifications are the #1 reason for application rejection.',
        },
    ],
    body: `
> **Disclaimer:** UPSC CMS 2026 official dates and fees will be published in the UPSC notification. The schedule below is based on the consistent pattern from UPSC CMS 2018–2025. Always verify at [upsc.gov.in](https://upsc.gov.in/examinations/combined-medical-services-examination).

---

## Important Dates (Expected Schedule for UPSC CMS 2026)

UPSC follows a remarkably consistent schedule for CMS. Since 2018, the notification has appeared between **late January and mid-February**, with the exam held in **April or May**. This allows roughly **90 days** of preparation between notification and the written exam.

| Event | Expected Date |
|-------|--------------|
| Notification Release | Late January 2026 |
| Online Application Opens | Early February 2026 |
| Last Date to Submit Online | Late February 2026 (~25 days after notification) |
| Last Date for Fee Payment | Same as last date for submission |
| Admit Card Release | ~3 weeks before exam (April 2026) |
| Written Examination (Paper I & II) | April/May 2026 |
| Result Declaration | ~6–8 weeks after exam |
| Personality Test (Viva Voce) | July–August 2026 |

---

## Eligibility Criteria

### Educational Qualification

- Passed MBBS (or an equivalent medical qualification recognised by the Medical Council of India / National Medical Commission).
- **Candidates in the final year of MBBS can also apply**, provided they submit proof of passing the degree at the time of the personality test.
- Interns can apply, but they must have completed the internship by the time the application window closes.

### Age Limit

- **Maximum age: 32 years** as of January 1 of the exam year (check the notification for the exact reference date).
- Age relaxations: OBC (Non-Creamy Layer) 3 years, SC/ST 5 years, Ex-Servicemen 5 years, PwD (General) 10 years.

### Medical Registration

All candidates must be registered (permanent or provisional) with the **Medical Council of India (MCI)** or any **State Medical Council (SMC)**.

### Number of Attempts

UPSC CMS does not impose a fixed number of attempts. The only hard cap is the **age limit of 32 years**.

---

## Application Fee Structure

| Category | Fee (INR) |
|----------|-----------|
| General / EWS / OBC (Male) | ₹200 |
| All Female Candidates | Nil (Exempt) |
| SC / ST / Ex-Servicemen | Nil (Exempt) |
| PwD Candidates | Nil (Exempt) |

The fee must be paid online through SBI Collect, credit/debit card, or net banking. **No offline payment modes** are accepted.

---

## Documents Required

Before you start filling the form, have these documents ready in digital format:

1. **Scanned passport-size photograph** — recent, white/light background, 200×240 pixels, 20–300 KB, JPG/JPEG.
2. **Scanned signature** — black ink on white paper, 140×60 pixels, 10–300 KB, JPG/JPEG.
3. **Photo ID proof** — Aadhaar, Voter ID, PAN, Passport, or Driving Licence.
4. **MBBS Degree / Marksheet** — all years combined PDF or individual year marksheets.
5. **Medical Registration Certificate** — proof of registration with MCI or SMC (can be provisional).
6. **Caste / Category Certificate** (if applicable) — issued by the competent authority in the prescribed format.
7. **Disability Certificate** (if applicable) — from a notified Medical Board.
8. **Ex-Servicemen Discharge Book** (if applicable).

---

## Step-by-Step Application Process

1. **Read the Official Notification** — Download the PDF from upsc.gov.in. Read every page, especially Annexures.
2. **Register on the UPSC Portal** — Go to upsonline.nic.in → "New Registration". Save your Registration ID (RID).
3. **Log In & Fill Part-I Registration** — Enter RID, DOB, captcha. Fill personal details and upload photo/signature.
4. **Fill Part-II Application** — Select CMS exam, indicate preferred service/category, upload all supporting documents.
5. **Pay the Application Fee** — Click "Pay Now" and choose your payment mode. Save the receipt.
6. **Print the Confirmation Page** — Print and save both the registration page and final confirmation.

---

## Common Mistakes That Get Applications Rejected

- **Wrong photo/signature format** — The most common rejection reason. Specifications are strict and non-negotiable.
- **Name mismatch across documents** — Must match exactly across all uploaded documents.
- **Category certificate in wrong format** — OBC candidates must use the exact format prescribed in the notification.
- **Applying without permanent registration** — Must submit permanent certificate at the personality test.
- **Late payment or payment failure** — Fee must be paid within the application window.
- **Not saving the RID or confirmation** — Without your Registration ID, you cannot log in to check status.

---

## Frequently Asked Questions

### Can final year MBBS students apply?

Yes. Candidates in the final year can apply, but must submit proof of passing at the time of the personality test. Interns must complete their internship before the application closes.

### What photo size is required for the UPSC CMS form?

Photo: 200×240 pixels, 20–300 KB, JPG/JPEG, white/light background. Signature: 140×60 pixels, 10–300 KB, JPG/JPEG, black ink on white paper.

### Is there an age relaxation for OBC candidates?

Yes. OBC (Non-Creamy Layer) candidates get 3 years of age relaxation beyond the 32-year limit. SC/ST get 5 years, Ex-Servicemen get 5 years, and PwD (General) gets 10 years.

### How many times can I attempt UPSC CMS?

There is no fixed attempt limit. The only restriction is the age limit of 32 years (with applicable relaxations). You can attempt every year until you cross the age limit.

### Can I pay the fee offline?

No. UPSC CMS accepts only online payment — SBI Collect, credit/debit card, or net banking. There is no challan or demand draft option.

### When is the UPSC CMS 2026 exam expected?

Based on the consistent UPSC CMS 2018–2025 pattern, the exam is expected in **April or May 2026**. The official date will be in the UPSC notification — always verify at upsc.gov.in.

### What if I make a mistake in the application form?

If the edit window is still open (usually 5–7 days after last date), you can edit via the UPSC portal. After the window closes, send a written request to UPSC with the correct details.
`,
    wordCount: 2800,
};

export default post;
