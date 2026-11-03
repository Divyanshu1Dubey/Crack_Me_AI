'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { analyticsAPI, extractApiErrorMessage } from '@/lib/api';
import {
  announcementStatus,
  campaignIsExpired,
  listRows,
  parseExpiryInput,
  toDateTimeLocalValue,
  type AnnouncementStatus,
} from '../_lib/adminHelpers';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Megaphone, Trash2, AlertCircle, CheckCircle2, X } from 'lucide-react';

/**
 * Uses the analytics announcements API (/api/analytics/announcements/):
 * that is the model the student header and dashboard read. This page used
 * to post {title, message, priority} to /api/questions/announcements/, a
 * different model whose required field is `body`, so every create failed
 * with 400 and nothing it stored ever reached a student.
 *
 * It lists every announcement (?scope=all: drafts, scheduled, deactivated
 * and expired ones too); the bare call returns only the live ones, so an
 * expired or deactivated announcement could not be found here to fix.
 */
interface AnnouncementItem {
  id: number;
  title: string;
  message?: string;
  priority?: string;
  is_active?: boolean;
  is_expired?: boolean;
  delivery_status?: string;
  scheduled_for?: string | null;
  expires_at?: string | null;
  created_at?: string;
}

const STATUS_BADGES: Record<AnnouncementStatus, { label: string; className: string }> = {
  live: { label: 'Live', className: 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300' },
  scheduled: { label: 'Scheduled', className: 'border-blue-500/40 text-blue-700 dark:text-blue-300' },
  draft: { label: 'Draft', className: 'text-muted-foreground' },
  inactive: { label: 'Deactivated', className: 'text-muted-foreground' },
  expired: { label: 'Expired', className: 'border-amber-500/40 text-amber-700 dark:text-amber-300' },
  failed: { label: 'Failed', className: 'border-destructive/40 text-destructive' },
};

/** Banner after an expiry change: is the announcement visible to students now? */
function expiryChangedText(row: AnnouncementItem | null | undefined, expiresAt: string | null): string {
  const what = expiresAt ? `Expiry set to ${new Date(expiresAt).toLocaleString()}.` : 'Expiry removed.';
  const status = row ? announcementStatus(row) : null;
  if (status === 'live') return `${what} Students see it now.`;
  if (status === 'inactive') return `${what} It is still deactivated: publish it again from Admin > Broadcast.`;
  if (status === 'draft') return `${what} It is a draft: publish it from Admin > Broadcast.`;
  if (status === 'scheduled') return `${what} Students see it from its scheduled time.`;
  return what;
}

export default function AdminAnnouncementsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  // Client-side admin gate (backend `IsAdminUser` is the authoritative RBAC).
  const isAdmin = !!user && (user.role === 'admin' || user.is_admin);

  const [announcements, setAnnouncements] = useState<AnnouncementItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState({
    title: '',
    message: '',
    priority: 'normal',
    expires_at: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [banner, setBanner] = useState<{ kind: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.replace('/login?next=' + encodeURIComponent('/admin/announcements'));
      return;
    }
    if (!isAdmin) {
      router.replace('/dashboard');
      return;
    }
    fetchAnnouncements();
  }, [authLoading, user, isAdmin, router]);

  // Every announcement, newest first (the backend returns up to 200).
  const fetchAnnouncements = async () => {
    try {
      const res = await analyticsAPI.getAnnouncements({ scope: 'all' });
      setAnnouncements(listRows<AnnouncementItem>(res.data));
    } catch (error) {
      console.error('Error fetching announcements:', error);
      setBanner({ kind: 'error', text: 'Could not load announcements.' });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.title.trim() || !formData.message.trim()) {
      setBanner({ kind: 'error', text: 'Title and message are required.' });
      return;
    }
    let expiresAt: string | undefined;
    if (formData.expires_at) {
      // A past expiry would create an announcement no student ever sees.
      const parsed = parseExpiryInput(formData.expires_at);
      if (!parsed.ok) {
        setBanner({ kind: 'error', text: parsed.message });
        return;
      }
      expiresAt = parsed.iso;
    }
    setSubmitting(true);
    try {
      await analyticsAPI.createAnnouncement({
        title: formData.title.trim(),
        message: formData.message.trim(),
        priority: formData.priority,
        ...(expiresAt ? { expires_at: expiresAt } : {}),
      });
      setBanner({ kind: 'success', text: 'Announcement published to students.' });
      setFormData({ title: '', message: '', priority: 'normal', expires_at: '' });
      await fetchAnnouncements();
    } catch (error: any) {
      console.error('Error creating announcement:', error);
      setBanner({
        kind: 'error',
        text: `Could not create announcement: ${extractApiErrorMessage(error?.response?.data, 'request failed')}`,
      });
    } finally {
      setSubmitting(false);
    }
  };

  // Hides a live announcement from students without deleting it
  // (PATCH is_active=false); Admin > Broadcast can publish it again.
  const [deactivatingId, setDeactivatingId] = useState<number | null>(null);
  const handleDeactivate = async (id: number) => {
    setDeactivatingId(id);
    try {
      await analyticsAPI.updateAnnouncement(id, { is_active: false });
      setBanner({ kind: 'success', text: 'Announcement deactivated. Students no longer see it; publish it again from Admin > Broadcast.' });
      await fetchAnnouncements();
    } catch (error: any) {
      console.error('Error deactivating announcement:', error);
      setBanner({
        kind: 'error',
        text: `Could not deactivate announcement: ${extractApiErrorMessage(error?.response?.data, 'request failed')}`,
      });
    } finally {
      setDeactivatingId(null);
    }
  };

  // Expiry editor (one row at a time): a later expiry brings an expired
  // announcement back for students; "Remove expiry" keeps it up for good.
  const [expiryEditId, setExpiryEditId] = useState<number | null>(null);
  const [expiryDraft, setExpiryDraft] = useState('');
  const [expirySavingId, setExpirySavingId] = useState<number | null>(null);

  const toggleExpiryEdit = (ann: AnnouncementItem) => {
    if (expiryEditId === ann.id) {
      setExpiryEditId(null);
      return;
    }
    setExpiryEditId(ann.id);
    setExpiryDraft(toDateTimeLocalValue(ann.expires_at));
  };

  const saveExpiry = async (id: number, removeExpiry = false) => {
    let expiresAt: string | null = null;
    if (!removeExpiry) {
      const parsed = parseExpiryInput(expiryDraft);
      if (!parsed.ok) {
        setBanner({ kind: 'error', text: parsed.message });
        return;
      }
      expiresAt = parsed.iso;
    }
    setExpirySavingId(id);
    try {
      const res = await analyticsAPI.updateAnnouncement(id, { expires_at: expiresAt });
      setExpiryEditId(null);
      setBanner({ kind: 'success', text: expiryChangedText(res?.data, expiresAt) });
      await fetchAnnouncements();
    } catch (error: any) {
      console.error('Error changing announcement expiry:', error);
      setBanner({
        kind: 'error',
        text: `Could not change the expiry: ${extractApiErrorMessage(error?.response?.data, 'request failed')}`,
      });
    } finally {
      setExpirySavingId(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this announcement?')) return;
    try {
      await analyticsAPI.deleteAnnouncement(id);
      setBanner({ kind: 'success', text: 'Announcement deleted.' });
      await fetchAnnouncements();
    } catch (error) {
      console.error('Error deleting announcement:', error);
      setBanner({ kind: 'error', text: 'Could not delete announcement.' });
    }
  };

  if (authLoading || !user) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] text-muted-foreground">
        Checking admin access…
      </div>
    );
  }

  if (!isAdmin) {
    return null;
  }

  // Inside the AppShell layout, .page-container already pads the page.
  return (
    <div className="p-4 sm:p-6 [.page-container_&]:p-0 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Megaphone className="w-6 h-6" /> Manage Announcements
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Create and manage announcements shown to users in the student header and dashboard.
        </p>
      </div>

      {/* Inline banner — no external toast library in package.json */}
      {banner && (
        <div
          role="alert"
          className={`rounded-md border p-3 flex items-start gap-2 ${
            banner.kind === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-300'
              : 'bg-destructive/10 border-destructive/30 text-destructive'
          }`}
        >
          {banner.kind === 'success' ? (
            <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          )}
          <span className="text-sm flex-1">{banner.text}</span>
          <button
            type="button"
            onClick={() => setBanner(null)}
            className="ml-2 hover:opacity-70"
            aria-label="Dismiss"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Create New Announcement</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Title</label>
              <Input
                required
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Announcement title"
                disabled={submitting}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Message</label>
              <textarea
                required
                rows={4}
                value={formData.message}
                onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                placeholder="Announcement body…"
                disabled={submitting}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Priority</label>
              <select
                value={formData.priority}
                onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                disabled={submitting}
                className="rounded-md border bg-background px-3 py-2 text-sm w-full"
              >
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Expires (optional)</label>
              <Input
                type="datetime-local"
                value={formData.expires_at}
                onChange={(e) => setFormData({ ...formData, expires_at: e.target.value })}
                disabled={submitting}
              />
            </div>
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create Announcement'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>All Announcements</CardTitle>
          <p className="text-xs text-muted-foreground">
            Newest first, including drafts, scheduled, deactivated and expired ones (campaigns from Admin &gt; Broadcast
            too). Students only see the Live ones.
          </p>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground py-4">Loading…</p>
          ) : announcements.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">No announcements found.</p>
          ) : (
            <div className="space-y-3">
              {announcements.map((ann) => {
                const status = announcementStatus(ann);
                const badge = STATUS_BADGES[status];
                // A deactivated row can also be past its expiry: say both.
                const alsoExpired = status !== 'expired' && campaignIsExpired(ann);
                // Same rule as Admin > Broadcast: drafts were never shown.
                const canDeactivate = ann.is_active !== false && (ann.delivery_status || 'draft') !== 'draft';
                const editingExpiry = expiryEditId === ann.id;
                const savingExpiry = expirySavingId === ann.id;
                return (
                  <div key={ann.id} className="border border-border rounded-md p-4 space-y-3">
                    <div className="flex flex-col sm:flex-row justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-base font-medium wrap-break-word">{ann.title}</h3>
                          <Badge variant="outline" className={badge.className}>{badge.label}</Badge>
                          {alsoExpired && (
                            <Badge variant="outline" className={STATUS_BADGES.expired.className}>{STATUS_BADGES.expired.label}</Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          Priority: <span className="font-medium">{ann.priority || 'normal'}</span>
                          {' · '}
                          Created: {ann.created_at ? new Date(ann.created_at).toLocaleString() : '—'}
                          {status === 'scheduled' && ann.scheduled_for && (
                            <>{' · '}Scheduled: {new Date(ann.scheduled_for).toLocaleString()}</>
                          )}
                          {ann.expires_at && (
                            <>{' · '}{campaignIsExpired(ann) ? 'Expired' : 'Expires'}: {new Date(ann.expires_at).toLocaleString()}</>
                          )}
                        </p>
                        <p className="text-sm mt-2 whitespace-pre-wrap wrap-break-word">{ann.message}</p>
                      </div>
                      <div className="flex flex-wrap gap-2 self-start">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => toggleExpiryEdit(ann)}
                          aria-expanded={editingExpiry}
                          disabled={savingExpiry}
                        >
                          Edit expiry
                        </Button>
                        {canDeactivate && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDeactivate(ann.id)}
                            disabled={deactivatingId === ann.id}
                          >
                            {deactivatingId === ann.id ? 'Deactivating…' : 'Deactivate'}
                          </Button>
                        )}
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => handleDelete(ann.id)}
                          aria-label="Delete announcement"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          <span className="sr-only">Delete</span>
                        </Button>
                      </div>
                    </div>
                    {editingExpiry && (
                      <div className="flex flex-wrap items-end gap-2 rounded-md border border-border bg-muted/30 p-3">
                        <label className="flex flex-col gap-1 text-xs font-medium">
                          New expiry
                          <Input
                            type="datetime-local"
                            value={expiryDraft}
                            onChange={(e) => setExpiryDraft(e.target.value)}
                            disabled={savingExpiry}
                            className="w-56 max-w-full"
                          />
                        </label>
                        <Button size="sm" onClick={() => saveExpiry(ann.id)} disabled={savingExpiry}>
                          {savingExpiry ? 'Saving…' : 'Save expiry'}
                        </Button>
                        {ann.expires_at && (
                          <Button size="sm" variant="outline" onClick={() => saveExpiry(ann.id, true)} disabled={savingExpiry}>
                            Remove expiry
                          </Button>
                        )}
                        <Button size="sm" variant="ghost" onClick={() => setExpiryEditId(null)} disabled={savingExpiry}>
                          Cancel
                        </Button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
