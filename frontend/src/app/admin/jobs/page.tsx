'use client';

import React, { useState, useEffect } from 'react';
import { jobsAPI } from '@/lib/api';

export default function AdminJobsPage() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [tracks, setTracks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState({
    title: '',
    hospital: '',
    location: '',
    description: '',
    eligibility_summary: '',
    exam_tracks: [] as number[],
    apply_link: '',
    salary: '',
  });

  const fetchJobs = async () => {
    try {
      const res = await jobsAPI.list();
      setJobs(res.data.results || res.data);
      
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
    fetchJobs();
  }, []);



  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await jobsAPI.create({ ...formData, admin_edited: true });
      fetchJobs();
      setFormData({
        title: '', hospital: '', location: '', description: '',
        eligibility_summary: '', exam_tracks: [], apply_link: '', salary: ''
      });
    } catch (error) {
      console.error(error);
      alert('Error creating job');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this job?')) return;
    try {
      await jobsAPI.remove(id);
      fetchJobs();
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-slate-900">Manage Job Postings</h1>
      
      <div className="bg-white p-6 rounded-lg border shadow-sm">
        <h2 className="text-xl font-semibold mb-4 text-slate-900">Create New Job</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-bold text-slate-900">Job Title</label>
            <input required value={formData.title} onChange={e => setFormData({...formData, title: e.target.value})} className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-slate-900" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-900">Hospital/Organization</label>
            <input required value={formData.hospital} onChange={e => setFormData({...formData, hospital: e.target.value})} className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-slate-900" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-900">Location</label>
            <input required value={formData.location} onChange={e => setFormData({...formData, location: e.target.value})} className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-slate-900" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-900">Salary (Optional)</label>
            <input value={formData.salary} onChange={e => setFormData({...formData, salary: e.target.value})} className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-slate-900" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-900">Application Link</label>
            <input required type="url" value={formData.apply_link} onChange={e => setFormData({...formData, apply_link: e.target.value})} className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-slate-900" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-900">Description</label>
            <textarea required rows={3} value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-slate-900" />
          </div>
          <div>
            <label className="block text-sm font-bold text-slate-900">Eligibility Summary</label>
            <textarea required rows={2} value={formData.eligibility_summary} onChange={e => setFormData({...formData, eligibility_summary: e.target.value})} className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border text-slate-900" />
          </div>
          <div>
            <label className="block text-sm font-bold mb-2 text-slate-900">Target Exam Tracks (Hold Ctrl/Cmd to select multiple)</label>
            <select
              multiple
              value={formData.exam_tracks.map(String)}
              onChange={(e) => {
                const selected = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                setFormData({ ...formData, exam_tracks: selected });
              }}
              className="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-2 border min-h-[100px] text-slate-900"
            >
              {tracks.map(t => (
                <option key={t.id} value={t.id} className="p-1">{t.name}</option>
              ))}
            </select>
          </div>
          <button type="submit" className="bg-indigo-700 hover:bg-indigo-800 text-white px-4 py-2 rounded font-bold transition-colors">Create Job</button>
        </form>
      </div>

      <div className="bg-white p-6 rounded-lg border shadow-sm">
        <h2 className="text-xl font-semibold mb-4 text-slate-900">Existing Jobs</h2>
        {loading ? <p>Loading...</p> : (
          <div className="space-y-4">
            {jobs.map(job => (
              <div key={job.id} className="flex justify-between items-start p-4 border rounded bg-slate-50">
                <div>
                  <h3 className="text-lg font-bold text-slate-900">{job.title} at {job.hospital}</h3>
                  <p className="text-sm font-medium text-slate-800 mb-2">{job.location} | {job.salary}</p>
                  <div className="flex gap-2 mt-1">
                    {job.exam_tracks?.map((trackId: number) => {
                      const t = tracks.find(x => x.id === trackId);
                      return t ? <span key={trackId} className="bg-indigo-200 text-indigo-900 text-xs px-2 py-1 rounded uppercase font-bold border border-indigo-300">{t.name}</span> : null;
                    })}
                  </div>
                </div>
                <button onClick={() => handleDelete(job.id)} className="text-red-700 hover:text-red-900 hover:bg-red-50 px-3 py-1 rounded font-bold transition-colors self-start">Delete</button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
