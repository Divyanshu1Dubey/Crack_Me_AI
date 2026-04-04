import Image from 'next/image';
import { cn } from '@/lib/utils';

interface CustomIconProps {
  name: string;
  label?: string;
  className?: string;
  size?: number;
  variant?: 'default' | 'active' | 'subtle';
}

const variantClasses: Record<NonNullable<CustomIconProps['variant']>, string> = {
  default: 'opacity-90 dark:invert dark:brightness-0',
  active: 'opacity-100 dark:invert dark:brightness-0',
  subtle: 'opacity-70 dark:invert dark:brightness-0',
};

export default function CustomIcon({
  name,
  label,
  className,
  size = 20,
  variant = 'default',
}: CustomIconProps) {
  const safeName = name.replace(/[^a-z0-9-_]+/gi, '').toLowerCase();
  const src = `/icons/custom/${safeName}.png`;

  return (
    <span className={cn('relative inline-flex shrink-0', className)} style={{ width: size, height: size }}>
      <Image
        src={src}
        alt={label || safeName.replace(/-/g, ' ')}
        fill
        sizes={`${size}px`}
        className={cn('object-contain', variantClasses[variant])}
      />
    </span>
  );
}
