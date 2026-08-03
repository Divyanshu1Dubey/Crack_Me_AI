'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { announcementsAPI, analyticsAPI } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Megaphone, Trash2, AlertCircle, CheckCircle2, X } from 'lucide-react';

interface AnnouncementItem {
  id: number;
  title: string;
  message?: string;
  body?: string;
  priority?: string;
  created_at?: string;
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

  const fetchAnnouncements = async () => {
    try {
      const res = await announcementsAPI.list();
      const data = res.data?.results || res.data || [];
      setAnnouncements(Array.isArray(data) ? (data as AnnouncementItem[]) : []);
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
    setSubmitting(true);
    try {
      await announcementsAPI.create({
        title: formData.title.trim(),
        message: formData.message.trim(),
        priority: formData.priority,
      });
      setBanner({ kind: 'success', text: 'Announcement created.' });
      setFormData({ title: '', message: '', priority: 'normal' });
      await fetchAnnouncements();
    } catch (error) {
      console.error('Error creating announcement:', error);
      setBanner({ kind: 'error', text: 'Could not create announcement. Check console for details.' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this announcement?')) return;
    try {
      await announcementsAPI.remove(id);
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

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Megaphone className="w-6 h-6" /> Manage Announcements
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Create and manage announcements shown to users. Backend enforces admin permissions.
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
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Creating…' : 'Create Announcement'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Existing Announcements</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground py-4">Loading…</p>
          ) : announcements.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">No announcements found.</p>
          ) : (
            <div className="space-y-3">
              {announcements.map((ann) => (
                <div
                  key={ann.id}
                  className="border border-border rounded-md p-4 flex flex-col sm:flex-row justify-between gap-3"
                >
                  <div className="flex-1 min-w-0">
                    <h3 className="text-base font-medium wrap-break-word">{ann.title}</h3>
                    <p className="text-xs text-muted-foreground mt-1">
                      Priority: <span className="font-medium">{ann.priority || 'normal'}</span>
                      {' · '}
                      Created: {ann.created_at ? new Date(ann.created_at).toLocaleString() : '—'}
                    </p>
                    <p className="text-sm mt-2 whitespace-pre-wrap wrap-break-word">{ann.message || ann.body}</p>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDelete(ann.id)}
                    className="self-start"
                    aria-label="Delete announcement"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span className="sr-only">Delete</span>
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
