'use client';

import Link from 'next/link';
import { Home, Search, ArrowLeft, BookOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function NotFound() {
  return (
    <div className="min-h-[calc(100vh-80px)] flex items-center justify-center p-4 sm:p-6 md:p-8">
      <div className="max-w-xl w-full text-center">
        <div
          className="inline-flex items-center justify-center w-20 h-20 sm:w-24 sm:h-24 rounded-3xl bg-primary/10 text-primary mb-6 sm:mb-8"
          aria-hidden="true"
        >
          <Search className="w-10 h-10 sm:w-12 sm:h-12" />
        </div>

        <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight mb-3 sm:mb-4">
          Page not found
        </h1>

        <p className="text-base sm:text-lg text-muted-foreground mb-8 sm:mb-10 max-w-md mx-auto">
          The page you&apos;re looking for doesn&apos;t exist, was moved, or you don&apos;t have
          access to it. Try one of these instead:
        </p>

        <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center mb-10 sm:mb-12">
          <Button asChild size="lg" className="min-h-12 px-6">
            <Link href="/">
              <Home className="w-4 h-4 mr-2" aria-hidden="true" />
              Go home
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline" className="min-h-12 px-6">
            <Link href="/questions">
              <BookOpen className="w-4 h-4 mr-2" aria-hidden="true" />
              Browse questions
            </Link>
          </Button>
        </div>

        <div className="text-sm text-muted-foreground">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1 hover:text-primary transition-colors focus-visible:outline-2 focus-visible:outline-primary focus-visible:outline-offset-2 rounded-sm"
          >
            <ArrowLeft className="w-3 h-3" aria-hidden="true" />
            Back to dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
