'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { datadogLogs } from '@datadog/browser-logs';
import { datadogRum } from '@datadog/browser-rum';
import { useAuth } from '@/lib/auth';
import { consent, type ConsentState } from '@/lib/consent';

type DatadogWindow = Window & {
  __CRACKCMS_DD_INIT__?: boolean;
};

const parseNumber = (value: string | undefined, fallback: number) => {
  if (!value) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

/**
 * Datadog RUM + browser logs.
 *
 * - Starts only after the visitor allows the `analytics` category (RUM and
 *   session replay used to start for everyone before any choice). Revoking
 *   consent later switches both SDKs to trackingConsent "not-granted".
 * - No `allowedTracingUrls`: with tracing on, the SDK adds x-datadog-* and
 *   traceparent headers to every API request, which the backend's
 *   CORS_ALLOW_HEADERS does not allow, so every preflight would fail.
 * - Only the opaque user id and role are attached to the session (no email
 *   or name).
 */
export default function DatadogInit() {
  const { user } = useAuth();
  const hasInit = useRef(false);
  const [analyticsAllowed, setAnalyticsAllowed] = useState(false);

  const config = useMemo(() => {
    const clientToken = process.env.NEXT_PUBLIC_DD_CLIENT_TOKEN || process.env.NEXT_PUBLIC_DATADOG_CLIENT_TOKEN || '';
    const applicationId = process.env.NEXT_PUBLIC_DD_APPLICATION_ID || process.env.NEXT_PUBLIC_DATADOG_APPLICATION_ID || '';
    const site = process.env.NEXT_PUBLIC_DD_SITE || 'datadoghq.com';
    const env = process.env.NEXT_PUBLIC_DD_ENV || process.env.NEXT_PUBLIC_DATADOG_ENV || process.env.NODE_ENV || 'production';
    const service = process.env.NEXT_PUBLIC_DD_SERVICE || process.env.NEXT_PUBLIC_DATADOG_SERVICE || 'crackcms-frontend';
    const version = process.env.NEXT_PUBLIC_DD_VERSION || process.env.NEXT_PUBLIC_DATADOG_VERSION || '';
    const sessionSampleRate = parseNumber(process.env.NEXT_PUBLIC_DD_SESSION_SAMPLE_RATE, 100);
    const sessionReplaySampleRate = parseNumber(process.env.NEXT_PUBLIC_DD_SESSION_REPLAY_SAMPLE_RATE, 20);
    const logSampleRate = parseNumber(process.env.NEXT_PUBLIC_DD_LOGS_SAMPLE_RATE, 100);

    return {
      clientToken,
      applicationId,
      site,
      env,
      service,
      version,
      sessionSampleRate,
      sessionReplaySampleRate,
      logSampleRate,
    };
  }, []);

  const configured = Boolean(config.clientToken && config.applicationId);

  // Track the visitor's analytics consent (stored decision + live changes).
  useEffect(() => {
    if (!configured) return;
    const apply = (state: ConsentState) => setAnalyticsAllowed(state.analytics === true);
    const off = consent.onChange(apply);
    const current = consent.read();
    if (current) apply(current);
    return off;
  }, [configured]);

  // Init on first grant; flip tracking consent on later changes.
  useEffect(() => {
    if (typeof window === 'undefined' || !configured) return;
    const win = window as DatadogWindow;

    if (hasInit.current || win.__CRACKCMS_DD_INIT__) {
      const trackingConsent = analyticsAllowed ? 'granted' : 'not-granted';
      try {
        datadogRum.setTrackingConsent(trackingConsent);
        datadogLogs.setTrackingConsent(trackingConsent);
      } catch {
        /* ignore */
      }
      return;
    }
    if (!analyticsAllowed) return;

    datadogRum.init({
      applicationId: config.applicationId,
      clientToken: config.clientToken,
      site: config.site,
      service: config.service,
      env: config.env,
      version: config.version || undefined,
      sessionSampleRate: config.sessionSampleRate,
      sessionReplaySampleRate: config.sessionReplaySampleRate,
      trackResources: true,
      trackLongTasks: true,
      trackUserInteractions: true,
      defaultPrivacyLevel: 'mask-user-input',
      trackingConsent: 'granted',
    });
    datadogRum.startSessionReplayRecording();

    datadogLogs.init({
      clientToken: config.clientToken,
      site: config.site,
      service: config.service,
      env: config.env,
      version: config.version || undefined,
      sessionSampleRate: config.logSampleRate,
      forwardErrorsToLogs: true,
      forwardConsoleLogs: ['error', 'warn'],
      trackingConsent: 'granted',
    });

    hasInit.current = true;
    win.__CRACKCMS_DD_INIT__ = true;
  }, [config, configured, analyticsAllowed]);

  useEffect(() => {
    if (!hasInit.current) return;

    if (!user || !analyticsAllowed) {
      datadogRum.clearUser();
      datadogLogs.clearUser();
      return;
    }

    const identity = {
      id: String(user.id),
      role: user.role,
    };
    datadogRum.setUser(identity);
    datadogLogs.setUser(identity);
  }, [user, analyticsAllowed]);

  return null;
}
