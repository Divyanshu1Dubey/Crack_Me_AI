import React from 'react';
import { Rocket } from 'lucide-react';
import Link from 'next/link';
import { Button } from './ui/button';

export function ComingSoon({ title = 'Coming Soon', message = 'We are working hard to bring this feature to you. Stay tuned!' }: { title?: string, message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center min-h-[400px] border border-dashed border-gray-300 rounded-2xl bg-gray-50/50 my-6">
      <div className="bg-indigo-100 p-4 rounded-full mb-6">
        <Rocket className="w-10 h-10 text-indigo-600" />
      </div>
      <h2 className="text-2xl font-bold text-gray-900 mb-2">{title}</h2>
      <p className="text-gray-500 max-w-md mb-6">
        {message}
      </p>
      <Link href="/dashboard">
        <Button variant="default">Return to Dashboard</Button>
      </Link>
    </div>
  );
}

export default ComingSoon;
