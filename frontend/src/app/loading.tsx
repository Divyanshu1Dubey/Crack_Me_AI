import EngagingLoader from '@/components/EngagingLoader';

export default function Loading() {
  return (
    <EngagingLoader
      title="Getting your exam cockpit ready..."
      subtitle="Loading high-yield questions, analytics, and personalized prep signals."
      fullScreen
    />
  );
}
