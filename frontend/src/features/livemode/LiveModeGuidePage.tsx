import { useQuery } from '@tanstack/react-query';

import { Markdown, withoutLeadingTitle } from '../../components/Markdown';
import { PageHeader } from '../../theme/slots';

/** Served by the API from docs/live-mode.md, public like the wheel beside it. */
export const LIVE_MODE_GUIDE_SOURCE = '/kit/live-mode.md';

async function fetchDoc(source: string): Promise<string> {
  const response = await fetch(source);
  if (!response.ok) throw new Error('This page could not be loaded. Try again later.');
  return response.text();
}

/** A Markdown file the API serves under /kit/, rendered in the app so learners can read it. */
export function KitDocPage({
  source,
  title,
  summary,
}: {
  source: string;
  title: string;
  summary: string;
}) {
  const doc = useQuery({ queryKey: ['kit-doc', source], queryFn: () => fetchDoc(source) });
  return (
    <div className="mx-auto max-w-page space-y-8 px-4 py-8 sm:px-6">
      <PageHeader title={title} summary={summary} />
      {doc.isPending && (
        <p role="status" className="m-0 text-ink-muted">
          Loading…
        </p>
      )}
      {doc.isError && (
        <p role="alert" className="m-0 text-danger">
          {doc.error.message}
        </p>
      )}
      {doc.data !== undefined && (
        <div className="max-w-measure font-reading text-lg">
          <Markdown>{withoutLeadingTitle(doc.data)}</Markdown>
        </div>
      )}
    </div>
  );
}

/** The live mode guide (docs/live-mode.md). */
export function LiveModeGuidePage() {
  return (
    <KitDocPage
      source={LIVE_MODE_GUIDE_SOURCE}
      title="Live mode"
      summary="Run your code against a real model, on your own machine, with your own key."
    />
  );
}
