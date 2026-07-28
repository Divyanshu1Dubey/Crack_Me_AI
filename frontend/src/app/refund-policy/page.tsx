import { LegalLayout, buildLegalMetadata } from '@/components/LegalLayout';
import type { Metadata } from 'next';

const title = 'Refund Policy — CrackCMS Premium Subscriptions';
const description = 'CrackCMS refund policy: eligibility window, AI token usage threshold, how to request a refund, and processing timelines.';
const canonical = '/refund-policy';

export const metadata: Metadata = buildLegalMetadata({ title, description, canonical });

export default function RefundPolicyPage() {
    return (
        <LegalLayout
            title={title}
            description={description}
            lastUpdated="July 21, 2026"
            canonical={canonical}
            schemaType="WebPage"
        >
            <h2>1. Refund Window</h2>
            <p>
                We want you to feel confident trying CrackCMS Premium. If our platform doesn&apos;t fit your
                study style, you can request a full refund within <strong>7 days</strong> of your
                purchase — provided fewer than <strong>10 AI tokens</strong> have been consumed on your
                account.
            </p>

            <h2>2. Eligibility</h2>
            <table>
                <thead>
                    <tr>
                        <th>Scenario</th>
                        <th>Refund eligible?</th>
                        <th>Refund amount</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Purchased &lt; 7 days ago, &lt; 10 AI tokens used</td>
                        <td>Yes</td>
                        <td>100%</td>
                    </tr>
                    <tr>
                        <td>Purchased &lt; 7 days ago, ≥ 10 AI tokens used</td>
                        <td>No (digital content consumed)</td>
                        <td>—</td>
                    </tr>
                    <tr>
                        <td>Purchased &gt; 7 days ago</td>
                        <td>No</td>
                        <td>—</td>
                    </tr>
                    <tr>
                        <td>Duplicate purchase (same account, same plan, 24h)</td>
                        <td>Yes (auto-merged or refunded)</td>
                        <td>100% of duplicate</td>
                    </tr>
                    <tr>
                        <td>Service outage &gt; 72 continuous hours</td>
                        <td>Yes (pro-rata)</td>
                        <td>Pro-rata</td>
                    </tr>
                    <tr>
                        <td>Fraud / unauthorised transaction</td>
                        <td>Yes</td>
                        <td>100% + chargeback assistance</td>
                    </tr>
                </tbody>
            </table>

            <h2>3. How to Request a Refund</h2>
            <ol>
                <li>Email <a href="mailto:crackwith.ai@gmail.com">crackwith.ai@gmail.com</a> from the address linked to your CrackCMS account.</li>
                <li>Include your registered email, transaction ID, and a brief reason.</li>
                <li>We respond within <strong>2 business days</strong>.</li>
            </ol>

            <h2>4. Processing Timelines</h2>
            <p>
                Approved refunds are credited back to the original payment method within <strong>5–10
                business days</strong>, depending on your bank or card issuer. UPI and net-banking refunds
                typically arrive within 3 business days.
            </p>

            <h2>5. Tokens &amp; Consumables</h2>
            <p>
                AI tokens are treated as digital consumables. Once 10+ tokens are consumed, the underlying
                digital content has been delivered and the purchase is final.
            </p>

            <h2>6. Subscription Auto-Renewal</h2>
            <p>
                Premium plans auto-renew unless cancelled before the renewal date. You can cancel anytime
                from <a href="/settings">Settings → Subscription</a>. Cancelling stops future renewals but
                does not retroactively refund the current term.
            </p>

            <h2>7. Disputes</h2>
            <p>
                If you dispute a charge with your bank or card issuer before contacting us, we may suspend
                your premium features pending resolution. Please reach out first — most issues are resolved
                within 48 hours.
            </p>

            <h2>8. Contact</h2>
            <p>
                <strong>Billing Team</strong><br />
                Email: <a href="mailto:crackwith.ai@gmail.com">crackwith.ai@gmail.com</a>
            </p>
        </LegalLayout>
    );
}
