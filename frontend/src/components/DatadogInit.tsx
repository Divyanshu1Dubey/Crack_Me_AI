'use client';

import { useEffect, useMemo, useRef } from 'react';
import { datadogLogs } from '@datadog/browser-logs';
import { datadogRum } from '@datadog/browser-rum';
import { useAuth } from '@/lib/auth';

type DatadogWindow = Window & {
  __CRACKCMS_DD_INIT__?: boolean;
};

const parseNumber = (value: string | undefined, fallback: number) => {
  if (!value) return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

export default function DatadogInit() {
  const { user } = useAuth();
  const hasInit = useRef(false);

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
    const apiBase = process.env.NEXT_PUBLIC_API_URL || '';

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
      apiBase,
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!config.clientToken || !config.applicationId) return;

    const win = window as DatadogWindow;
    if (hasInit.current || win.__CRACKCMS_DD_INIT__) return;

    const allowedTracingUrls = config.apiBase ? [new URL(config.apiBase).origin] : undefined;

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
      allowedTracingUrls,
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
    });

    hasInit.current = true;
    win.__CRACKCMS_DD_INIT__ = true;
  }, [config]);

  useEffect(() => {
    if (!hasInit.current) return;

    if (!user) {
      datadogRum.clearUser();
      datadogLogs.clearUser();
      return;
    }

    const identity = {
      id: String(user.id),
      name: user.username,
      email: user.email,
      role: user.role,
    };
    datadogRum.setUser(identity);
    datadogLogs.setUser(identity);
  }, [user]);

  return null;
}
