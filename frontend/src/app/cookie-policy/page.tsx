import { LegalLayout, buildLegalMetadata } from '@/components/LegalLayout';
import type { Metadata } from 'next';

const title = 'Cookie Policy — CrackCMS';
const description = 'How CrackCMS uses cookies and similar technologies — essential cookies, analytics cookies, and how to control them.';
const canonical = '/cookie-policy';

export const metadata: Metadata = buildLegalMetadata({ title, description, canonical });

export default function CookiePolicyPage() {
    return (
        <LegalLayout
            title={title}
            description={description}
            lastUpdated="July 21, 2026"
            canonical={canonical}
        >
            <h2>1. What Are Cookies?</h2>
            <p>
                Cookies are small text files placed on your device when you visit a website. They help the
                site remember your actions and preferences (such as login, theme, language) over a period
                of time. CrackCMS also uses similar technologies including <em>localStorage</em>,
                <em>sessionStorage</em>, and IndexedDB.
            </p>

            <h2>2. Cookies We Use</h2>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Purpose</th>
                        <th>Provider</th>
                        <th>Type</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Essential</td>
                        <td>Authentication, CSRF token, session integrity</td>
                        <td>CrackCMS</td>
                        <td>First-party</td>
                    </tr>
                    <tr>
                        <td>Preferences</td>
                        <td>Theme (light/dark), sidebar collapse, exam track selection</td>
                        <td>CrackCMS</td>
                        <td>localStorage</td>
                    </tr>
                    <tr>
                        <td>Analytics</td>
                        <td>Aggregate usage telemetry, error reporting</td>
                        <td>Datadog, Google Analytics 4</td>
                        <td>First-party proxies</td>
                    </tr>
                    <tr>
                        <td>PWA</td>
                        <td>Offline cache, install prompt state</td>
                        <td>CrackCMS service worker</td>
                        <td>First-party</td>
                    </tr>
                </tbody>
            </table>

            <h2>3. Cookies We Do NOT Use</h2>
            <ul>
                <li>No advertising cookies (no AdSense, no Facebook Pixel, no cross-site tracking).</li>
                <li>No third-party retargeting pixels.</li>
                <li>No social-media tracking cookies unless you explicitly click a social share button.</li>
            </ul>

            <h2>4. Controlling Cookies</h2>
            <p>
                You can clear or block cookies in your browser settings. Note that disabling essential
                cookies will prevent login and theme preferences from working. We honour the
                <strong>Do Not Track</strong> and <strong>Global Privacy Control</strong> browser signals.
            </p>

            <h2>5. Updates to This Policy</h2>
            <p>
                We will update this page if our cookie usage changes. The "Last updated" date at the top
                reflects the latest revision.
            </p>
        </LegalLayout>
    );
}
