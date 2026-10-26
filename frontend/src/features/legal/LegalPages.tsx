import { Link } from '@tanstack/react-router';
import type { ReactNode } from 'react';

import { PageHeader } from '../../theme/slots';
import { LINK } from '../auth/fields';

/** Where people write about their data. The owner replaces it before launch. */
export const PRIVACY_CONTACT = 'privacy@forgeway.dev';
/** The date the current wording took effect. */
export const LEGAL_UPDATED = '26 October 2026';

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="m-0 text-xl">{title}</h2>
      {children}
    </section>
  );
}

function Page({
  title,
  summary,
  children,
}: {
  title: string;
  summary: string;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-page space-y-8 px-4 py-8 sm:px-6">
      <PageHeader title={title} summary={summary} />
      <div className="max-w-measure space-y-8 [&_li]:my-1 [&_p]:m-0 [&_ul]:m-0 [&_ul]:pl-6">
        {children}
        <p className="text-sm text-ink-muted">Last updated {LEGAL_UPDATED}.</p>
      </div>
    </div>
  );
}

const contact = (
  <a href={`mailto:${PRIVACY_CONTACT}`} className={LINK}>
    {PRIVACY_CONTACT}
  </a>
);

/** The privacy policy: what Forgeway stores, why, for how long, and who else handles it. */
export function PrivacyPage() {
  return (
    <Page
      title="Privacy policy"
      summary="What Forgeway keeps about you, why, for how long, and what you can do about it."
    >
      <Section title="Who we are">
        <p>
          Forgeway is a small learning site run by one person in the United Kingdom, who is the
          controller of your data under UK GDPR. Write to {contact} about anything on this page.
        </p>
      </Section>

      <Section title="What we keep">
        <ul>
          <li>
            <strong>Your account:</strong> your email address, the display name you choose, and your
            password as a one-way hash (we never see or store the password itself).
          </li>
          <li>
            <strong>Your learning:</strong> your progress, the code you submit with its grading
            report, autosaved drafts, XP, badges, talents, certificates and your settings (mode,
            colour scheme, time zone and path).
          </li>
          <li>
            <strong>The Pro waitlist,</strong> if you join it: your address and which plan you were
            interested in. We do not email you from it until Pro opens.
          </li>
          <li>
            <strong>Your IP address,</strong> briefly, to limit how often sign-up, sign-in and
            password resets can be tried. These records go after a day.
          </li>
        </ul>
        <p>
          We use this to run your account, grade your code and show your progress, which is the
          service you signed up for (the lawful basis is our contract with you), and to keep the
          site safe from abuse (our legitimate interest).
        </p>
      </Section>

      <Section title="What we do not do">
        <p>
          There are no adverts, no analytics or tracking scripts, and no selling or sharing of your
          data. Your code is used to grade your attempt and is never used to train AI models.
        </p>
      </Section>

      <Section title="Cookies and local storage">
        <p>
          We set one cookie, which keeps you signed in for up to 14 days. It is strictly necessary,
          so we do not ask for consent. Your browser also keeps your mode and colour scheme, so the
          site looks right before you sign in; that never leaves your device.
        </p>
      </Section>

      <Section title="Who else handles it">
        <ul>
          <li>
            <strong>Our server host,</strong> where the site and its database run, in a data centre
            the host operates for us.
          </li>
          <li>
            <strong>Resend,</strong> which delivers our emails (address confirmations and password
            resets), so it sees your address and the email we send.
          </li>
          <li>
            <strong>Cloudflare,</strong> which sits in front of the site to protect it, so it sees
            your IP address and the requests you make.
          </li>
        </ul>
        <p>
          Some of these providers may process data outside the UK; where they do, they use the
          safeguards UK law requires.
        </p>
      </Section>

      <Section title="How long we keep it">
        <ul>
          <li>Your account and learning data: until you delete your account.</li>
          <li>Accounts whose email address is never confirmed: deleted after 7 days.</li>
          <li>Rate-limit records: a day. Server logs: up to 30 days.</li>
          <li>
            Backups: nightly copies of the database are kept for up to five weeks, so deleted data
            leaves them within that time.
          </li>
        </ul>
      </Section>

      <Section title="Your rights">
        <p>
          You can download everything we hold about you, as a JSON file, and delete your account at
          any time, from{' '}
          <Link to="/profile" className={LINK}>
            your profile
          </Link>{' '}
          (Settings). Deleting removes your account and everything in it straight away, and your
          public certificate links stop working. You can also ask us to correct your data, or object
          to how we use it, by writing to {contact}. If you are unhappy with our answer, you can
          complain to the Information Commissioner&apos;s Office (ico.org.uk).
        </p>
      </Section>
    </Page>
  );
}

/** The terms of use: plain rules for a small learning site. */
export function TermsPage() {
  return (
    <Page title="Terms of use" summary="The rules for using Forgeway, in plain English.">
      <Section title="The service">
        <p>
          Forgeway teaches AI engineering through exercises that grade your code. It is run by one
          person in the United Kingdom. By creating an account you agree to these terms and to the{' '}
          <Link to="/privacy" className={LINK}>
            privacy policy
          </Link>
          .
        </p>
      </Section>

      <Section title="Your account">
        <ul>
          <li>You need a working email address, and one account per person.</li>
          <li>Keep your password to yourself; you are responsible for what your account does.</li>
          <li>You can delete your account at any time from your profile.</li>
        </ul>
      </Section>

      <Section title="Fair use">
        <ul>
          <li>
            Submit code to learn, not to attack the site, the grader or other learners, or to get
            round the limits on how often you can submit.
          </li>
          <li>
            Do not use the grader to run anything unrelated to the exercise, such as mining or
            scanning.
          </li>
          <li>We may suspend or close accounts that break these rules.</li>
        </ul>
      </Section>

      <Section title="Your code and our content">
        <p>
          The code you write is yours. You let us store and run it to grade it and show it back to
          you. The exercises, tests and course material are ours, and you may not republish them.
        </p>
      </Section>

      <Section title="Plans">
        <p>
          The free plan covers the foundations and the first exercises of every track. Pro is not on
          sale yet: joining the waitlist costs nothing and commits you to nothing.
        </p>
      </Section>

      <Section title="Certificates">
        <p>
          A certificate says you passed a track&apos;s exercises on Forgeway. It is not an
          accredited qualification. If you make one public, anyone with its link can see your name
          on it.
        </p>
      </Section>

      <Section title="No guarantees">
        <p>
          We work to keep Forgeway available and correct, but it is provided as it is, and we may
          change or withdraw parts of it. As far as the law allows, we are not liable for indirect
          losses from using it. Nothing here limits your rights as a consumer.
        </p>
      </Section>

      <Section title="Changes and contact">
        <p>
          If these terms change in a way that matters, we will say so on the site. They are governed
          by the law of England and Wales. Write to {contact} with any question.
        </p>
      </Section>
    </Page>
  );
}
