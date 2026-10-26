import { LoaderCircle } from 'lucide-react';
import type { ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'quiet';

const VARIANTS: Record<Variant, string> = {
  primary:
    'bg-accent text-on-accent border border-accent hover:bg-accent-strong hover:border-accent-strong',
  secondary: 'bg-transparent text-ink border border-line-strong hover:bg-sunken',
  quiet:
    'bg-transparent text-ink-secondary border border-transparent hover:text-ink hover:bg-sunken',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  /** Keeps the label's width and overlays a spinner. */
  loading?: boolean;
}

export function Button({
  variant = 'primary',
  loading = false,
  className = '',
  disabled,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled === true || loading}
      aria-busy={loading || undefined}
      className={`relative inline-flex min-h-11 items-center justify-center gap-2 rounded-control px-4 font-ui text-base font-medium transition-colors duration-fast disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${className}`}
      {...rest}
    >
      <span className={`inline-flex items-center gap-2 ${loading ? 'opacity-0' : ''}`}>
        {children}
      </span>
      {loading && <LoaderCircle aria-hidden="true" className="absolute h-5 w-5 animate-spin" />}
    </button>
  );
}
