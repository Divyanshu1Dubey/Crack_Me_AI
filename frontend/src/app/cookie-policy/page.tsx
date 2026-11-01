import { LegalLayout, buildLegalMetadata } from '@/components/LegalLayout';
import type { Metadata } from 'next';
import ManageCookiesButton from './ManageCookiesButton';

const title = 'Cookie Policy — CrackCMS';
const description = 'How CrackCMS uses cookies and similar technologies — essential cookies, analytics cookies, and how to control them.';
const canonical = '/cookie-policy';

export const metadata: Metadata = buildLegalMetadata({ title, description, canonical });

export default function CookiePolicyPage() {
    return (
        <LegalLayout
            title={title}
            description={description}
            lastUpdated="November 1, 2026"
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
            <p>
                Nothing in the Analytics or Product analytics &amp; advertising rows below is loaded until
                you allow that category in the cookie banner. If you choose <strong>Reject all</strong>,
                those scripts are never loaded and no events are sent to them.
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Purpose</th>
                        <th>Provider</th>
                        <th>When it runs</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Essential</td>
                        <td>Sign-in session, CSRF protection, single-device session, your cookie choice</td>
                        <td>CrackCMS</td>
                        <td>Always (first-party cookies and localStorage)</td>
                    </tr>
                    <tr>
                        <td>Preferences</td>
                        <td>Theme (light/dark), sidebar collapse, exam track selection</td>
                        <td>CrackCMS</td>
                        <td>Always (localStorage)</td>
                    </tr>
                    <tr>
                        <td>Analytics</td>
                        <td>Page views, scroll depth, performance and error monitoring, masked session replay, and our own first-party usage log (anonymous visitor ID)</td>
                        <td>Google Analytics 4, Microsoft Clarity, Datadog RUM, CrackCMS</td>
                        <td>Only after you allow &quot;Analytics&quot;</td>
                    </tr>
                    <tr>
                        <td>Product analytics &amp; advertising</td>
                        <td>Product funnels and retention cohorts; Google AdSense ads if we enable them</td>
                        <td>PostHog, Google AdSense</td>
                        <td>Only after you allow &quot;Product analytics &amp; advertising&quot;</td>
                    </tr>
                    <tr>
                        <td>Cookieless page counts</td>
                        <td>Aggregate page-view counts; sets no cookies and stores no personal data</td>
                        <td>Simple Analytics</td>
                        <td>Always</td>
                    </tr>
                    <tr>
                        <td>PWA</td>
                        <td>Install prompt state (the service worker does not cache pages for offline use)</td>
                        <td>CrackCMS service worker</td>
                        <td>Always (first-party)</td>
                    </tr>
                </tbody>
            </table>

            <h2>3. Cookies We Do NOT Use</h2>
            <ul>
                <li>No third-party retargeting pixels.</li>
                <li>No social-media tracking cookies unless you explicitly click a social share button.</li>
            </ul>

            <h2>3a. Advertising Cookies (AdSense)</h2>
            <p>
                CrackCMS does not currently show ads. If we enable Google AdSense in future, the ad script
                will load only after you allow &quot;Product analytics &amp; advertising&quot;; Google may then
                set advertising cookies under its own privacy policy. You can manage personalised ads at{' '}
                <a href="https://adssettings.google.com" target="_blank" rel="noopener noreferrer">Google Ads Settings</a>.
            </p>

            <h2>4. Controlling Cookies</h2>
            <p>
                You can review or change your choice at any time:
            </p>
            <ManageCookiesButton />
            <p>
                You can also clear or block cookies in your browser settings. Note that disabling essential
                cookies will prevent login and theme preferences from working.
            </p>

            <h2>5. Updates to This Policy</h2>
            <p>
                We will update this page if our cookie usage changes. The "Last updated" date at the top
                reflects the latest revision.
            </p>
        </LegalLayout>
    );
}
