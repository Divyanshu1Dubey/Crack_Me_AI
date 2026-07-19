'use client';

import React, { useState, useEffect } from 'react';
import { announcementsAPI } from '@/lib/api';

export default function AdminAnnouncementsPage() {
  const [announcements, setAnnouncements] = useState<any[]>([]);
  const [tracks, setTracks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState({
    title: '',
    body: '',
    exam_tracks: [] as number[],
  });

  const fetchAnnouncements = async () => {
    try {
      const res = await announcementsAPI.list();
      const data = res.data?.results || res.data || [];
      setAnnouncements(Array.isArray(data) ? data : []);
      // Quick fetch for tracks using generic API wrapper (or fetch directly)
      const resTracks = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.9:8000/api'}/questions/exam-tracks/`);
      const trackData = await resTracks.json();
      setTracks(trackData?.results || trackData || []);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnnouncements();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await announcementsAPI.create(formData);
      fetchAnnouncements();
      setFormData({ title: '', body: '', exam_tracks: [] });
    } catch (error) {
      console.error(error);
      alert('Error creating announcement');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this announcement?')) return;
    try {
      await announcementsAPI.remove(id);
      fetchAnnouncements();
    } catch (error) {
      console.error(error);
      alert('Error deleting announcement');
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Manage Announcements</h1>
      
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <h2 className="text-xl font-semibold mb-4">Create New Announcement</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Title</label>
            <input
              type="text"
              required
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Body</label>
            <textarea
              required
              rows={4}
              value={formData.body}
              onChange={(e) => setFormData({ ...formData, body: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Target Exam Tracks (Hold Ctrl/Cmd to select multiple)</label>
            <select
              multiple
              value={formData.exam_tracks.map(String)}
              onChange={(e) => {
                const selected = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                setFormData({ ...formData, exam_tracks: selected });
              }}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border min-h-[100px]"
            >
              {tracks.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
            <p className="text-xs text-gray-500 mt-1">Leave empty to target all students regardless of track.</p>
          </div>
          <button
            type="submit"
            className="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            Create Announcement
          </button>
        </form>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200">
        <div className="p-6">
          <h2 className="text-xl font-semibold mb-4">Existing Announcements</h2>
          {loading ? (
            <p>Loading...</p>
          ) : (
            <div className="space-y-4">
              {announcements.map((ann) => (
                <div key={ann.id} className="border p-4 rounded-md flex justify-between items-start">
                  <div>
                    <h3 className="text-lg font-medium">{ann.title}</h3>
                    <p className="text-sm text-gray-500 mb-2">Target: {ann.target_exam_track} | Created: {new Date(ann.created_at).toLocaleString()}</p>
                    <p className="text-gray-700">{ann.body}</p>
                  </div>
                  <button
                    onClick={() => handleDelete(ann.id)}
                    className="text-red-600 hover:text-red-900 text-sm font-medium"
                  >
                    Delete
                  </button>
                </div>
              ))}
              {announcements.length === 0 && <p className="text-gray-500">No announcements found.</p>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
