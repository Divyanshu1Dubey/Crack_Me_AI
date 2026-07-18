'use client';

import React, { useState, useEffect } from 'react';
import { jobsAPI } from '@/lib/api';

export default function AdminJobsPage() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [formData, setFormData] = useState({
    title: '',
    hospital: '',
    location: '',
    description: '',
    eligibility_summary: '',
    exam_track_tags: [] as string[],
    apply_link: '',
    salary: '',
  });

  const fetchJobs = async () => {
    try {
      const res = await jobsAPI.list();
      setJobs(res.data.results || res.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const handleTrackChange = (track: string) => {
    setFormData(prev => ({
      ...prev,
      exam_track_tags: prev.exam_track_tags.includes(track) 
        ? prev.exam_track_tags.filter(t => t !== track)
        : [...prev.exam_track_tags, track]
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await jobsAPI.create({ ...formData, admin_edited: true });
      fetchJobs();
      setFormData({
        title: '', hospital: '', location: '', description: '',
        eligibility_summary: '', exam_track_tags: [], apply_link: '', salary: ''
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
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Manage Job Postings</h1>
      
      <div className="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <h2 className="text-xl font-semibold mb-4">Create New Job</h2>
        <form onSubmit={handleSubmit} className="space-y-4 grid grid-cols-2 gap-4">
          <div className="col-span-1">
            <label className="block text-sm font-medium">Job Title</label>
            <input required value={formData.title} onChange={e => setFormData({...formData, title: e.target.value})} className="mt-1 block w-full rounded border p-2" />
          </div>
          <div className="col-span-1">
            <label className="block text-sm font-medium">Hospital/Organization</label>
            <input required value={formData.hospital} onChange={e => setFormData({...formData, hospital: e.target.value})} className="mt-1 block w-full rounded border p-2" />
          </div>
          <div className="col-span-1">
            <label className="block text-sm font-medium">Location</label>
            <input required value={formData.location} onChange={e => setFormData({...formData, location: e.target.value})} className="mt-1 block w-full rounded border p-2" />
          </div>
          <div className="col-span-1">
            <label className="block text-sm font-medium">Salary (Optional)</label>
            <input value={formData.salary} onChange={e => setFormData({...formData, salary: e.target.value})} className="mt-1 block w-full rounded border p-2" />
          </div>
          <div className="col-span-2">
            <label className="block text-sm font-medium">Application Link</label>
            <input required type="url" value={formData.apply_link} onChange={e => setFormData({...formData, apply_link: e.target.value})} className="mt-1 block w-full rounded border p-2" />
          </div>
          <div className="col-span-2">
            <label className="block text-sm font-medium">Description</label>
            <textarea required rows={3} value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} className="mt-1 block w-full rounded border p-2" />
          </div>
          <div className="col-span-2">
            <label className="block text-sm font-medium">Eligibility Summary</label>
            <input value={formData.eligibility_summary} onChange={e => setFormData({...formData, eligibility_summary: e.target.value})} className="mt-1 block w-full rounded border p-2" placeholder="e.g. MBBS with 1 yr internship" />
          </div>
          <div className="col-span-2">
            <label className="block text-sm font-medium mb-2">Target Exam Tracks (Tags)</label>
            <div className="flex gap-4">
              {['cms', 'neet_pg', 'fmge', 'usmle'].map(track => (
                <label key={track} className="flex items-center gap-1">
                  <input type="checkbox" checked={formData.exam_track_tags.includes(track)} onChange={() => handleTrackChange(track)} />
                  {track.toUpperCase()}
                </label>
              ))}
            </div>
          </div>
          <div className="col-span-2">
            <button type="submit" className="bg-indigo-600 text-white px-4 py-2 rounded font-medium">Create Job</button>
          </div>
        </form>
      </div>

      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="text-xl font-semibold mb-4">Existing Jobs</h2>
        {loading ? <p>Loading...</p> : (
          <div className="space-y-4">
            {jobs.map(job => (
              <div key={job.id} className="border p-4 rounded-md flex justify-between">
                <div>
                  <h3 className="text-lg font-medium">{job.title} at {job.hospital}</h3>
                  <p className="text-sm text-gray-500">{job.location} | {job.salary}</p>
                  <div className="flex gap-2 mt-2">
                    {job.exam_track_tags?.map((tag: string) => (
                      <span key={tag} className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded uppercase">{tag}</span>
                    ))}
                  </div>
                </div>
                <button onClick={() => handleDelete(job.id)} className="text-red-600 hover:text-red-900 font-medium self-start">Delete</button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
