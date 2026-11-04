import { Link } from '@tanstack/react-router';
import { Check } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';

import { usePublicConfig } from '../../api/hooks';
import type { CheckResult as CheckResultData } from '../../api/types';
import { CheckResult } from '../../components/CheckResult';
import { ProMark } from '../../components/ProMark';
import { Toggle } from '../../components/Toggle';
import { BranchOverview } from '../../theme/slots';
import { useLexicon } from '../../theme/useTheme';
import { activeBilling, priceLines, type Period } from './billing';
import { catalogueCounts, useCatalogue } from './useCatalogue';

const DEFAULT_FREE_PER_TRACK = 3;

// Links styled as the house Button variants (Button itself renders a <button>).
const LINK_BASE =
  'inline-flex min-h-11 items-center justify-center gap-2 rounded-control px-4 font-ui text-base font-medium no-underline transition-colors duration-fast';
const PRIMARY_LINK = `${LINK_BASE} border border-accent bg-accent text-on-accent hover:border-accent-strong hover:bg-accent-strong`;
const SECONDARY_LINK = `${LINK_BASE} border border-line-strong text-ink hover:bg-sunken`;

/**
 * A real result: the checks of the foundations' tool-calling loop run against the known-wrong
 * solution with no step cap (content/.../tool-use/wrong/unbounded-loop). Titles are the exercise's
 * own; the message is the one its hidden test gives.
 */
const EXAMPLE_CHECKS: CheckResultData[] = [
  {
    id: 'one-round',
    title: 'Runs a tool and sends its result back to get the answer',
    passed: true,
    message: '',
    output: '',
  },
  {
    id: 'several-calls',
    title: 'Handles several calls in one turn, in order, and chains rounds',
    passed: true,
    message: '',
    output: '',
  },
  {
    id: 'tool-errors',
    title: 'A failing or unknown tool becomes an error result the model sees',
    passed: true,
    message: '',
    output: '',
  },
  {
    id: 'step-cap',
    title: 'Stops at max_steps with a clear error',
    passed: false,
    message: 'The loop kept calling the model long after max_steps; it must stop.',
    output: '',
  },
];

/** Sets the document title and meta description while the page is shown. */
export function useDocumentHead(title: string, description: string) {
  useEffect(() => {
    const previousTitle = document.title;
    let meta = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    const created = meta === null;
    if (meta === null) {
      meta = document.createElement('meta');
      meta.name = 'description';
      document.head.append(meta);
    }
    const previousDescription = meta.content;
    document.title = title;
    meta.content = description;
    return () => {
      document.title = previousTitle;
      if (created) meta.remove();
      else meta.content = previousDescription;
    };
  }, [title, description]);
}

function Section({
  id,
  eyebrow,
  heading,
  children,
}: {
  id: string;
  eyebrow: string;
  heading: string;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="border-t border-line-subtle py-12 sm:py-16">
      <p className="label-caps m-0 text-accent-strong">{eyebrow}</p>
      <h2 id={id} className="small-caps-heading m-0 mt-2 max-w-measure text-2xl sm:text-3xl">
        {heading}
      </h2>
      <div className="mt-6">{children}</div>
    </section>
  );
}

function StartLinks() {
  const lexicon = useLexicon();
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Link to="/register" className={PRIMARY_LINK}>
        {lexicon.landing.start}
      </Link>
      <Link to="/sign-in" className={SECONDARY_LINK}>
        {lexicon.signIn}
      </Link>
    </div>
  );
}

function Hero({ perTrack }: { perTrack: number }) {
  const copy = useLexicon().landing;
  return (
    <section aria-labelledby="landing-title" className="py-12 sm:py-20">
      <p className="label-caps m-0 text-ink-muted">{copy.heroEyebrow}</p>
      <h1
        id="landing-title"
        className="small-caps-heading m-0 mt-3 max-w-[18ch] text-3xl sm:text-4xl"
      >
        {copy.heroTitle}
      </h1>
      <p className="m-0 mt-6 max-w-measure font-reading text-lg text-ink-secondary">
        {copy.heroLead}
      </p>
      <div className="mt-8">
        <StartLinks />
      </div>
      <p className="m-0 mt-4 text-sm text-ink-muted">{copy.heroNote(perTrack)}</p>
    </section>
  );
}

function Grading() {
  const copy = useLexicon().landing;
  const passed = EXAMPLE_CHECKS.filter((check) => check.passed).length;
  return (
    <Section id="landing-grading" eyebrow={copy.gradingEyebrow} heading={copy.gradingHeading}>
      <div className="grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-12">
        <div className="space-y-6">
          <p className="m-0 max-w-measure font-reading text-lg">{copy.gradingLead}</p>
          <ol className="m-0 list-none space-y-4 p-0">
            {copy.gradingSteps.map((step, index) => (
              <li
                key={step.title}
                className="grid grid-cols-[2rem_minmax(0,1fr)] gap-x-3 border-t border-line-subtle pt-4"
              >
                <span className="tabular font-display text-lg text-ink-muted">{index + 1}</span>
                <div>
                  <h3 className="m-0 font-ui text-base font-semibold">{step.title}</h3>
                  <p className="m-0 mt-1 text-ink-secondary">{step.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
        <figure aria-label={copy.gradingExampleLabel} className="m-0 space-y-3">
          <div className="space-y-4 rounded-panel border border-line-subtle bg-raised p-4 sm:p-6">
            <p className="tabular m-0 font-semibold">
              Not yet: {passed} of {EXAMPLE_CHECKS.length} checks passed
            </p>
            <ul className="m-0 list-none space-y-4 p-0">
              {EXAMPLE_CHECKS.map((check) => (
                <li key={check.id} className="border-t border-line-subtle pt-4">
                  <CheckResult check={check} />
                </li>
              ))}
            </ul>
          </div>
          <figcaption className="max-w-measure text-sm text-ink-muted">
            {copy.gradingExampleCaption}
          </figcaption>
        </figure>
      </div>
    </Section>
  );
}

function SecurityPathLink() {
  return <Link to="/security">{useLexicon().securityPath.link}</Link>;
}

function Tracks() {
  const copy = useLexicon().landing;
  const catalogue = useCatalogue();
  let body: ReactNode;
  if (catalogue.isPending) {
    body = (
      <p role="status" className="m-0 text-ink-muted">
        Loading…
      </p>
    );
  } else if (catalogue.isError) {
    body = <p className="m-0 max-w-measure text-ink-secondary">{copy.tracksUnavailable}</p>;
  } else {
    const counts = catalogueCounts(catalogue.data.branches);
    body = (
      <div className="space-y-10">
        <p className="m-0 max-w-measure font-reading text-lg">
          {copy.tracksSummary(
            counts.tracks,
            counts.projects,
            counts.exercises,
            counts.capstones,
            counts.primers,
          )}
        </p>
        <BranchOverview branches={catalogue.data.branches} startFolded />
        <p className="m-0">
          <SecurityPathLink />
        </p>
      </div>
    );
  }
  return (
    <Section id="landing-tracks" eyebrow={copy.tracksEyebrow} heading={copy.tracksHeading}>
      {body}
    </Section>
  );
}

function Different() {
  const copy = useLexicon().landing;
  const liveRuns = usePublicConfig().data?.live_runs ?? false;
  return (
    <Section id="landing-different" eyebrow={copy.differentEyebrow} heading={copy.differentHeading}>
      <div className="grid gap-x-12 sm:grid-cols-2">
        {copy.different.map((point) => (
          <div key={point.title} className="border-t border-line-strong py-5">
            <h3 className="m-0 text-lg">{point.title}</h3>
            <p className="m-0 mt-2 max-w-measure text-ink-secondary">{point.body}</p>
          </div>
        ))}
      </div>
      {liveRuns ? <p className="m-0 max-w-measure text-ink-secondary">{copy.liveInApp}</p> : null}
    </Section>
  );
}

function Ticks({ items }: { items: readonly string[] }) {
  return (
    <ul className="m-0 list-none space-y-2 p-0">
      {items.map((item) => (
        <li key={item} className="flex items-start gap-2">
          <Check aria-hidden="true" className="mt-1 h-4 w-4 shrink-0 text-accent-strong" />
          {item}
        </li>
      ))}
    </ul>
  );
}

function Plans({ perTrack }: { perTrack: number }) {
  const lexicon = useLexicon();
  const copy = lexicon.landing;
  const billing = activeBilling(usePublicConfig().data);
  // Annual is the pre-selected plan; monthly is one click away (docs/plans/billing.md).
  const [period, setPeriod] = useState<Period>('annual');
  const prices = billing === null ? null : priceLines(billing, period, copy);
  return (
    <Section id="landing-plans" eyebrow={copy.plansEyebrow} heading={copy.plansHeading}>
      <div className="grid gap-10 md:grid-cols-2 md:gap-0">
        <div className="space-y-5 md:pr-10">
          <h3 className="m-0 text-xl">{copy.freeTitle}</h3>
          <Ticks items={copy.freeItems(perTrack)} />
          <Link to="/register" className={SECONDARY_LINK}>
            {copy.plansCreateAccount}
          </Link>
        </div>
        <div className="space-y-5 border-t border-line-strong pt-10 md:border-l md:border-t-0 md:pl-10 md:pt-0">
          <h3 className="m-0 flex items-center gap-3 text-xl">
            {lexicon.proPageTitle}
            <ProMark />
          </h3>
          <Ticks items={lexicon.proIncludes} />
          {prices === null ? (
            <>
              <p className="m-0 max-w-measure text-ink-secondary">{copy.plansWaitlistNote}</p>
              <Link to="/register" className={PRIMARY_LINK}>
                {copy.plansCreateAccount}
              </Link>
            </>
          ) : (
            <>
              <Toggle
                legend={copy.plansPeriodLegend}
                value={period}
                options={[
                  { value: 'annual', label: copy.plansAnnualLabel },
                  { value: 'monthly', label: copy.plansMonthlyLabel },
                ]}
                onChange={setPeriod}
              />
              <p className="m-0 flex flex-wrap items-baseline gap-x-3">
                <span className="tabular text-2xl font-semibold">{prices.price}</span>
                {period === 'annual' && prices.saving !== null && (
                  <span className="text-ink-secondary">{prices.saving}</span>
                )}
              </p>
              {prices.trial !== null && <p className="m-0 max-w-measure">{prices.trial}</p>}
              <Link to="/pro" className={PRIMARY_LINK}>
                {prices.trial === null ? copy.plansChoosePro : copy.plansStartTrial}
              </Link>
            </>
          )}
        </div>
      </div>
    </Section>
  );
}

function Faq() {
  const copy = useLexicon().landing;
  return (
    <Section id="landing-faq" eyebrow={copy.faqEyebrow} heading={copy.faqHeading}>
      <div className="max-w-measure">
        {copy.faq.map((item) => (
          <div key={item.title} className="border-t border-line-subtle py-5">
            <h3 className="m-0 font-ui text-base font-semibold">{item.title}</h3>
            <p className="m-0 mt-2 text-ink-secondary">{item.body}</p>
          </div>
        ))}
      </div>
    </Section>
  );
}

/** The public face of `/` for visitors who are not signed in. */
export function LandingPage() {
  const copy = useLexicon().landing;
  const config = usePublicConfig();
  const perTrack = config.data?.free_exercises_per_branch ?? DEFAULT_FREE_PER_TRACK;
  useDocumentHead(copy.documentTitle, copy.metaDescription);

  return (
    <div className="mx-auto max-w-page px-4 sm:px-6">
      <Hero perTrack={perTrack} />
      <Grading />
      <Tracks />
      <Different />
      <Plans perTrack={perTrack} />
      <Faq />
      <section aria-labelledby="landing-final" className="border-t-2 border-ink py-12 sm:py-16">
        <h2 id="landing-final" className="small-caps-heading m-0 text-2xl sm:text-3xl">
          {copy.finalHeading}
        </h2>
        <p className="m-0 mt-3 max-w-measure font-reading text-lg text-ink-secondary">
          {copy.finalBody}
        </p>
        <div className="mt-6">
          <StartLinks />
        </div>
      </section>
    </div>
  );
}
