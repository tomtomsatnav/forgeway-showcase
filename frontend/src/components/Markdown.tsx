import type { ComponentPropsWithoutRef, ElementType } from 'react';
import ReactMarkdown, { type Components, type ExtraProps } from 'react-markdown';

type Props<T extends ElementType> = ComponentPropsWithoutRef<T> & ExtraProps;

/** Style an element, dropping react-markdown's `node` prop so it never reaches the DOM. */
function styled<T extends ElementType>(Tag: T, className: string) {
  return function Styled({ node: _node, ...props }: Props<T>) {
    const Element: ElementType = Tag;
    return <Element className={className} {...props} />;
  };
}

/** Raw HTML in content is never rendered: react-markdown drops it unless a plugin opts in. */
const BLOCK: Components = {
  h1: styled('h1', 'mb-6 mt-0 font-display text-2xl text-ink small-caps-heading'),
  h2: styled('h2', 'mb-3 mt-8 font-display text-xl text-ink small-caps-heading'),
  h3: styled('h3', 'mb-2 mt-6 font-display text-lg text-ink'),
  p: styled('p', 'mb-6 mt-0'),
  ul: styled('ul', 'mb-6 mt-0 list-disc space-y-2 pl-6'),
  ol: styled('ol', 'mb-6 mt-0 list-decimal space-y-2 pl-6'),
  blockquote: styled(
    'blockquote',
    'mb-6 ml-0 mt-0 border-l-2 border-accent pl-4 text-ink-secondary',
  ),
  hr: styled('hr', 'my-8 border-0 border-t border-line-subtle'),
  // Focusable so keyboard users can scroll a long line.
  pre: ({ node: _node, ...props }: Props<'pre'>) => (
    <pre
      tabIndex={0}
      className="mb-6 mt-0 overflow-x-auto rounded-control bg-sunken p-4 font-mono text-sm leading-6 text-ink [&_code]:bg-transparent [&_code]:p-0"
      {...props}
    />
  ),
  code: styled('code', 'rounded-control bg-sunken px-1.5 py-0.5 font-mono text-[0.875em]'),
  a: ({ node: _node, ...props }: Props<'a'>) => {
    return (
      <a
        className="text-accent-strong underline underline-offset-2"
        target="_blank"
        rel="noreferrer noopener"
        {...props}
      />
    );
  },
  table: ({ node: _node, ...props }: Props<'table'>) => {
    return (
      <div className="mb-6 overflow-x-auto">
        <table className="w-full border-collapse text-left" {...props} />
      </div>
    );
  },
  th: styled('th', 'border-b border-line-strong px-3 py-2 font-ui font-semibold'),
  td: styled('td', 'border-b border-line-subtle px-3 py-2'),
};

const INLINE: Components = { ...BLOCK, p: styled('span', '') };

/** Remove a leading level-1 heading, for briefs whose page already shows the title. */
export function withoutLeadingTitle(source: string): string {
  return source.replace(/^\s*# [^\n]*(\n|$)/, '').replace(/^\s*\n/, '');
}

interface MarkdownProps {
  children: string;
  /** Render paragraphs as spans, for short strings such as hints. */
  inline?: boolean;
}

export function Markdown({ children, inline = false }: MarkdownProps) {
  return <ReactMarkdown components={inline ? INLINE : BLOCK}>{children}</ReactMarkdown>;
}
