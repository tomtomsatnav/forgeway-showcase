import { Link } from '@tanstack/react-router';
import type { ReactNode } from 'react';

import { usePublicConfig } from '../../api/hooks';
import { PageHeader } from '../../theme/slots';
import { LINK } from '../auth/fields';

/** Where people write about their data, and about anything else. */
export const PRIVACY_CONTACT = 'privacy@forgeway.dev';
export const HELLO_CONTACT = 'hello@forgeway.dev';
/** The date the current wording took effect. Keep in step with the API's TERMS_VERSION. */
export const LEGAL_UPDATED = '3 November 2026';
/** Who sells Forgeway Pro (a sole trader). The address comes from LATTICE_TRADER_ADDRESS through
 * /api/config; billing stays off until it is set, and these pages show the placeholder. The owner
 * fills in the ICO number before launch. */
export const TRADER_NAME = '[TRADER NAME]';
export const TRADING_AS = 'Forgeway';
export const TRADER = `${TRADER_NAME}, trading as ${TRADING_AS}`;
export const TRADER_ADDRESS = '[VIRTUAL OFFICE ADDRESS]';
export const ICO_NUMBER = '[ICO REGISTRATION NUMBER]';

function useTraderAddress(): string {
  return usePublicConfig().data?.trader_address ?? TRADER_ADDRESS;
}
const SERVER_HOST = '[SERVER HOST AND COUNTRY]';

function Section({ title, id, children }: { title: string; id?: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-4 space-y-3">
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

/** A table that scrolls sideways on a narrow screen, reachable by keyboard when it does. */
function Table({ label, head, rows }: { label: string; head: string[]; rows: ReactNode[][] }) {
  return (
    <div
      role="region"
      aria-label={label}
      tabIndex={0}
      className="overflow-x-auto rounded-control focus-visible:outline"
    >
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr>
            {head.map((cell) => (
              <th
                key={cell}
                scope="col"
                className="border-b border-line-strong px-3 py-2 align-bottom font-semibold"
              >
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, c) =>
                c === 0 ? (
                  <th
                    key={c}
                    scope="row"
                    className="border-b border-line-subtle px-3 py-2 align-top font-semibold"
                  >
                    {cell}
                  </th>
                ) : (
                  <td key={c} className="border-b border-line-subtle px-3 py-2 align-top">
                    {cell}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const mail = (address: string) => (
  <a href={`mailto:${address}`} className={LINK}>
    {address}
  </a>
);
const contact = mail(PRIVACY_CONTACT);
const hello = mail(HELLO_CONTACT);

/** The trader details the E-Commerce Regulations 2002 (reg 6) and the Companies Act 2006
 * (s.1201) ask for, shown on every legal page. */
export function TraderDetails() {
  const traderAddress = useTraderAddress();
  return (
    <Section title="Who we are" id="trader">
      <p>
        Forgeway is run by {TRADER}, a sole trader in the United Kingdom, who is the controller of
        your personal data under UK GDPR.
      </p>
      <ul>
        <li>
          <strong>Address for documents:</strong> {traderAddress}
        </li>
        <li>
          <strong>Email:</strong> {hello} (anything) or {contact} (your data)
        </li>
        <li>
          <strong>Registered with the Information Commissioner&apos;s Office:</strong> {ICO_NUMBER}
        </li>
      </ul>
    </Section>
  );
}

/** How to complain to us, and what we do with it (DPA 2018 s.164A). Shared by both pages. */
function ComplaintsProcedure() {
  return (
    <Section title="Complaints" id="complaints">
      <p>
        If you are unhappy with anything we do, including how we use your data, please tell us
        first, by email to {contact} (data) or {hello} (anything else). We will:
      </p>
      <ul>
        <li>acknowledge your complaint within 30 days;</li>
        <li>look into it, and ask you for anything more we need;</li>
        <li>tell you what we found and what we will do, without undue delay;</li>
        <li>keep a record of the complaint and how it was resolved.</li>
      </ul>
      <p>
        If you are not satisfied with our answer, you can complain about data protection to the
        Information Commissioner&apos;s Office (
        <a href="https://ico.org.uk/make-a-complaint/" className={LINK}>
          ico.org.uk/make-a-complaint
        </a>
        , 0303 123 1113). You can also go to the ICO without complaining to us first. For other
        disputes, see &ldquo;Law and disputes&rdquo; in the{' '}
        <Link to="/terms" hash="disputes" className={LINK}>
          terms
        </Link>
        .
      </p>
    </Section>
  );
}

/** The privacy notice (UK GDPR Art 13): what Forgeway keeps, why, for how long, who else
 * handles it and what you can do about it. */
export function PrivacyPage() {
  return (
    <Page
      title="Privacy policy"
      summary="What Forgeway keeps about you, why, for how long, and what you can do about it."
    >
      <TraderDetails />

      <Section title="What we keep">
        <ul>
          <li>
            <strong>Your account:</strong> your email address, the display name you choose, your
            password as a one-way hash (we never see or store the password itself), which version of
            these terms you accepted and when, and whether you want emails about offers.
          </li>
          <li>
            <strong>Your learning:</strong> your progress, the code you submit with its grading
            report, autosaved drafts, XP, badges, talents, certificates and your settings (mode,
            colour scheme, time zone and path).
          </li>
          <li>
            <strong>Live runs,</strong> if you use them: the files you run, your program&apos;s
            output, and each model call&apos;s token counts and cost.
          </li>
          <li>
            <strong>The Pro waitlist,</strong> if you join it: your address, which plan you were
            interested in, and when you joined.
          </li>
          <li>
            <strong>Your subscription,</strong> if you subscribe to Pro: your Stripe customer and
            subscription references, your plan, its status and dates, your billing country, and a
            record of the consent you gave before paying (when, the exact wording and the plan).
            Your card details go straight to Stripe; we never see or store them.
          </li>
          <li>
            <strong>Your IP address,</strong> briefly, to limit how often sign-up, sign-in and
            password resets can be tried, and in server logs.
          </li>
          <li>
            <strong>What you write to us,</strong> such as a question, a request about your data or
            a complaint.
          </li>
        </ul>
      </Section>

      <Section title="Why we use it, and the lawful basis" id="purposes">
        <Table
          label="Purposes and lawful bases"
          head={['Purpose', 'Lawful basis (UK GDPR Art 6)']}
          rows={[
            [
              'Running your account, grading your code, showing your progress and certificates',
              'Contract: it is the service you signed up for',
            ],
            ['Running live runs you start', 'Contract'],
            [
              'Service emails: confirming your address, password resets, subscription confirmations, trial and renewal reminders, failed payments, cancellations',
              'Contract, and the law for the subscription notices',
            ],
            ['Taking payments and running your subscription', 'Contract'],
            ['Keeping tax and accounting records', 'Legal obligation'],
            [
              'Keeping the record of your consent to start Pro straight away, as evidence if a claim is made',
              'Legitimate interests (defending legal claims)',
            ],
            [
              'Keeping the site safe: rate limits, the human check at sign-up, Cloudflare, server logs',
              'Legitimate interests (preventing abuse and fraud)',
            ],
            [
              'Emails about Forgeway offers, only to people who have started a trial or a subscription and have not opted out',
              'Legitimate interests, with the "soft opt-in" in PECR regulation 22',
            ],
            [
              'One email to the waitlist when Pro opens',
              'Legitimate interests (you asked to hear)',
            ],
            ['Answering your requests and complaints', 'Legal obligation and legitimate interests'],
          ]}
        />
        <p>
          You can object to anything we do on the basis of legitimate interests by writing to{' '}
          {contact}. You can stop emails about offers at any time: untick the box in your profile,
          or use the unsubscribe link in any such email. Service emails never carry offers.
        </p>
      </Section>

      <Section title="Live runs and AI" id="ai">
        <p>
          A live run sends your current files and the messages your program sends to Anthropic, PBC,
          in the United States, which runs the model as our processor. Anthropic does not train its
          models on them and deletes them within 30 days (up to 2 years only if its safety systems
          flag them). We show you this before your first live run. We keep each run&apos;s files and
          output for 30 days, and its usage records (tokens and cost) for 13 months. Nothing from a
          live run is used for grading.
        </p>
        <p>
          Grading runs your code against tests on our own server; no AI model judges it. Local live
          mode runs on your own computer with your own API key, and nothing from it reaches us.
        </p>
      </Section>

      <Section title="Payments" id="payments">
        <p>
          Stripe takes payments for Pro, runs the subscription, calculates tax and sends receipts.
          It receives your name, email address, billing address and card details. Stripe acts as our
          processor for running payments, and as an independent controller for its own fraud
          prevention and its anti-money-laundering and financial-law duties, for which its own{' '}
          <a href="https://stripe.com/gb/privacy" className={LINK}>
            privacy policy
          </a>{' '}
          applies.
        </p>
      </Section>

      <Section title="What we do not do">
        <p>
          There are no adverts, no analytics or tracking scripts, and no selling or sharing of your
          data. Your code is never used to train AI models, by us or by Anthropic. No decision with
          legal or similarly significant effects is made about you by automated means: grading
          decides whether an exercise is passed and when a certificate is issued, and a certificate
          is not an accredited qualification.
        </p>
      </Section>

      <Section title="Cookies and local storage" id="cookies">
        <ul>
          <li>
            <strong>
              <code>lattice_session</code>
            </strong>{' '}
            (cookie): keeps you signed in, for up to 14 days or until you sign out. Strictly
            necessary.
          </li>
          <li>
            <strong>
              <code>__cf_bm</code>
            </strong>{' '}
            (cookie, set by Cloudflare): helps tell people from bots, for 30 minutes. Strictly
            necessary for security.
          </li>
          <li>
            <strong>
              <code>lattice.theme</code>
            </strong>{' '}
            (local storage): your mode and colour scheme, so the site looks right before you sign
            in.
          </li>
          <li>
            <strong>
              <code>lattice.workspace-columns</code>
            </strong>{' '}
            (local storage): the widths you drag the workspace columns to.
          </li>
          <li>
            <strong>The human check</strong> on the sign-up page is Cloudflare Turnstile, which runs
            in a frame from Cloudflare and sets no cookie on this site.
          </li>
        </ul>
        <p>
          These are strictly necessary or keep a preference you chose, and local storage never
          leaves your device, so we do not ask for consent. There is nothing for analytics or
          advertising. Signing out removes the session cookie; your browser&apos;s settings clear
          the rest (look for &ldquo;cookies and site data&rdquo;).
        </p>
      </Section>

      <Section title="Who else handles it" id="recipients">
        <p>
          These providers handle data for us under contract. Where data leaves the UK, the safeguard
          each uses is named.
        </p>
        <Table
          label="Processors and transfers"
          head={['Who', 'What they do and see', 'Where', 'Safeguard for the transfer']}
          rows={[
            [
              'Our server host',
              'Runs the server where the site, the database and its backups live',
              SERVER_HOST,
              'UK adequacy, where outside the UK',
            ],
            [
              'Cloudflare, Inc.',
              'Sits in front of the site to protect it (your IP address and requests) and runs the human check at sign-up',
              'United States and its global network',
              'UK Addendum to the EU Standard Contractual Clauses',
            ],
            [
              'Resend',
              'Delivers our emails, so sees your address and each email',
              'United States',
              'UK Extension to the EU-US Data Privacy Framework',
            ],
            [
              'Stripe',
              'Payments and subscriptions (also an independent controller, see Payments)',
              'United States and Ireland',
              'UK Extension to the EU-US Data Privacy Framework',
            ],
            [
              'Anthropic, PBC',
              'Runs the model for live runs: your files and your program’s messages',
              'United States',
              'UK Addendum to the EU Standard Contractual Clauses',
            ],
          ]}
        />
        <p>
          Our fonts are served from our own server, so your browser does not contact Google. We may
          also disclose data where the law requires it.
        </p>
      </Section>

      <Section title="How long we keep it" id="retention">
        <ul>
          <li>Your account and learning data: until you delete your account.</li>
          <li>Accounts whose email address is never confirmed: deleted after 7 days.</li>
          <li>
            Emailed links: until they expire (24 hours to confirm an address, 15 minutes to reset a
            password, 12 months to unsubscribe), then removed within a day.
          </li>
          <li>Sign-in sessions: 14 days, or until you sign out.</li>
          <li>Live runs: files and output for 30 days; usage records for 13 months.</li>
          <li>The waitlist: 12 months from joining, or until you delete your account.</li>
          <li>Rate-limit records: a day. Server logs: 30 days.</li>
          <li>
            Your subscription details: until you delete your account (which also ends any
            subscription).
          </li>
          <li>
            The record of your consent to start Pro straight away: six years from when you gave it,
            even if you delete your account. On deletion we remove your email and name from it,
            keeping only the wording, when you agreed, the plan and the Stripe references.
          </li>
          <li>
            Invoices and payment records: six years after the end of the tax year they belong to, as
            tax law requires, even if you delete your account. Stripe holds them, and keeps its own
            billing records under its own retention policy, which we do not control.
          </li>
          <li>
            Messages and complaints you send us: two years after the matter is closed; the
            complaints log, three years.
          </li>
          <li>
            Backups: nightly copies of the database are kept for up to five weeks, and a copy taken
            before each update until three later updates, so deleted data leaves them within that
            time.
          </li>
        </ul>
      </Section>

      <Section title="Your rights">
        <ul>
          <li>
            <strong>Access and portability:</strong> download everything we hold about you as a JSON
            file, which other services can read, from{' '}
            <Link to="/profile" className={LINK}>
              your profile
            </Link>{' '}
            (Settings).
          </li>
          <li>
            <strong>Correction:</strong> change your email address in your profile, or ask us to
            correct anything else.
          </li>
          <li>
            <strong>Erasure:</strong> delete your account at any time from your profile. It removes
            your account and everything in it straight away, and your public certificate links stop
            working, except the records above that the law or a possible claim needs us to keep.
          </li>
          <li>
            <strong>Objection and restriction:</strong> object to how we use your data, or ask us to
            pause using it, by writing to {contact}. You can always stop offers.
          </li>
        </ul>
        <p>
          We answer within a month. Forgeway is for adults: if we learn an account belongs to
          someone under 18, we delete it.
        </p>
      </Section>

      <ComplaintsProcedure />
    </Page>
  );
}

/** The terms of use, including Pro subscriptions and the cancellation policy. */
export function TermsPage() {
  const traderAddress = useTraderAddress();
  return (
    <Page title="Terms of use" summary="The rules for using Forgeway, in plain English.">
      <TraderDetails />

      <Section title="The service">
        <p>
          Forgeway teaches AI engineering through exercises that grade your code. By creating an
          account you agree to these terms. How we use your data is in the{' '}
          <Link to="/privacy" className={LINK}>
            privacy policy
          </Link>
          .
        </p>
      </Section>

      <Section title="Who can use Forgeway">
        <ul>
          <li>You must be 18 or over. We ask you to confirm this when you sign up.</li>
          <li>Forgeway is for your own learning, as a consumer.</li>
          <li>You need a working email address, and one account per person.</li>
          <li>Keep your password to yourself; you are responsible for what your account does.</li>
          <li>You can delete your account at any time from your profile.</li>
        </ul>
      </Section>

      <Section title="Plans">
        <p>
          The free plan covers the foundations and the first exercises of every track, and costs
          nothing. Forgeway Pro adds the capstone projects, the guided projects, every other
          exercise, live runs (where offered) and public certificates. Until Pro is on sale, joining
          the waitlist costs nothing and commits you to nothing.
        </p>
      </Section>

      <Section title="Forgeway Pro subscriptions">
        <ul>
          <li>
            <strong>Who you buy from.</strong> Pro is sold by {TRADER}, {traderAddress}. Payments
            are taken by Stripe; we never see your card details.
          </li>
          <li>
            <strong>Price.</strong> Pro costs the price shown on the Pro page when you subscribe:
            £19 a month or £190 a year. Prices include any VAT that applies.
          </li>
          <li>
            <strong>Free trial.</strong> New subscribers get a free trial (7 days unless the Pro
            page says otherwise). A card is needed to start it, nothing is charged during it, and
            the first payment is taken on the date shown before you subscribe unless you cancel
            before then. One free trial per person.
          </li>
          <li>
            <strong>Renewal.</strong> Your subscription renews automatically at the end of each
            month or year, and the card on file is charged, until you cancel. We email you before
            your trial ends and before each annual renewal.
          </li>
          <li>
            <strong>Changing plan or pausing.</strong> You can switch between monthly and annual
            from your profile (Manage billing); the difference is prorated. You can pause for up to
            three months: nothing is charged and Pro is off while paused.
          </li>
          <li>
            <strong>Failed payments.</strong> If a payment fails we try again over the following
            days and you keep Pro meanwhile. If it still fails, your subscription ends and your
            account returns to the free plan.
          </li>
          <li>
            <strong>Price changes.</strong> If the price changes, we tell you by email at least 30
            days before it applies to you, and you can cancel before then.
          </li>
          <li>
            Whatever happens to your subscription, everything you have passed, and any certificate
            already public, stays yours.
          </li>
        </ul>
      </Section>

      <Section title="Cancellation policy" id="cancellation">
        <p>
          You can cancel at any time, online, from your profile (Manage billing), in a few clicks.
          We may offer you a pause first; you never have to take it. Cancelling stops future
          payments: you keep Pro until the end of the period you have paid for, and we email you a
          confirmation within 24 hours. Cancelling during the free trial means you are never
          charged. Payments already made for a period that has started are not refunded, except as
          described here or as the law requires.
        </p>
        <p>
          <strong>Your right to cancel within 14 days.</strong> UK law usually gives you 14 days
          from the contract to cancel. Pro is digital content you can use straight away, so before
          you subscribe we ask you to tick a box agreeing that your access starts at once and
          acknowledging that you then lose that 14-day right. We record when you agreed and repeat
          it in your confirmation email. Your other rights as a consumer, for example if the service
          is faulty or not as described, are unaffected.
        </p>
        <p>
          <strong>Cancelling after a trial ends or a yearly renewal.</strong> From 1 January 2027,
          you can also cancel within 14 days after your free trial turns into a paid subscription,
          and within 14 days after each yearly renewal. This right cannot be given up. Use the
          &ldquo;Withdraw from contract&rdquo; control on your profile, or email {hello}: your
          subscription ends at once and the payment just taken is refunded in full within 14 days.
        </p>
        <p>
          <strong>Customers in the European Union</strong> can withdraw from the contract within 14
          days using the clearly labelled &ldquo;Withdraw from contract&rdquo; control on their
          profile. The contract ends at once and any payment is refunded within 14 days. You can
          also tell us by email at {contact}, or by sending the model cancellation form below.
        </p>
      </Section>

      <Section title="Model cancellation form" id="cancellation-form">
        <p className="text-sm text-ink-secondary">
          Complete and return this form only if you wish to cancel the contract.
        </p>
        <div className="space-y-2 rounded-panel border border-line-strong p-4">
          <p>
            To: {TRADER}, {traderAddress}, {contact}
          </p>
          <p>
            I/We [*] hereby give notice that I/We [*] cancel my/our [*] contract for the supply of
            the following digital content [*]/service [*]: Forgeway Pro
          </p>
          <p>Ordered on [*] / received on [*]:</p>
          <p>Name of consumer(s):</p>
          <p>Address of consumer(s):</p>
          <p>Signature of consumer(s) (only if this form is notified on paper):</p>
          <p>Date:</p>
          <p className="text-sm text-ink-secondary">[*] Delete as appropriate.</p>
        </div>
      </Section>

      <Section title="Your rights under consumer law" id="consumer-rights">
        <p>
          The Consumer Rights Act 2015 says Forgeway must be as described, fit for purpose and of
          satisfactory quality, and that we provide it with reasonable care and skill. If it is not,
          tell us: we will fix it or, if we cannot, reduce the price or refund you. If something we
          supply damages your device or other digital content because we did not take reasonable
          care, we will repair the damage or compensate you. Nothing in these terms takes away these
          rights. Citizens Advice can tell you more.
        </p>
      </Section>

      <Section title="Fair use, and live runs" id="fair-use">
        <ul>
          <li>
            Submit code to learn, not to attack the site, the grader or other learners, or to get
            round the limits on how often you can submit.
          </li>
          <li>
            Do not use the grader to run anything unrelated to the exercise, such as mining or
            scanning.
          </li>
          <li>
            Live runs call Anthropic&apos;s model on our account, within the monthly and daily
            limits shown in the workspace. Use them for the exercises, and follow Anthropic&apos;s{' '}
            <a href="https://www.anthropic.com/legal/aup" className={LINK}>
              Acceptable Use Policy
            </a>
            : no harmful, illegal or abusive content, and no attempts to get round its safeguards.
          </li>
        </ul>
      </Section>

      <Section title="Suspending or closing an account" id="suspension">
        <p>
          If you break these terms, we may suspend or close your account. We will tell you why and
          give you a reasonable chance to put things right first, unless we must act at once to
          protect the site, other learners or the law. If we close a Pro account without it being
          your fault, or end the service altogether, we refund the unused part of any period you
          have paid for.
        </p>
      </Section>

      <Section title="Changes to the service or these terms" id="changes">
        <p>
          We improve Forgeway all the time, and may change or withdraw parts of it. If we make a
          change to the terms or to Pro that matters to you, we email you at least 30 days before it
          takes effect and ask you to accept the new terms. If you do not want to continue, you can
          cancel before then and we refund the unused part of any period you have paid for. Changes
          we must make for legal or security reasons may take effect sooner; we will tell you as
          soon as we can.
        </p>
      </Section>

      <Section title="Your code and our content" id="licences">
        <ul>
          <li>
            The code you write is yours. You let us store and run it to grade it and to show it back
            to you, and, if you make a certificate public, to show your name on it.
          </li>
          <li>
            The exercises, tests and course material are ours or our licensors&apos;. While you have
            an account we give you a personal, non-transferable licence to use them for your own
            learning. You may not republish, sell or share them, or use them to train an AI model.
          </li>
          <li>If you send us feedback or ideas, we may use them without owing you anything.</li>
        </ul>
      </Section>

      <Section title="Certificates">
        <p>
          A certificate says you passed a track&apos;s exercises on Forgeway. It is not an
          accredited qualification. If you make one public, anyone with its link can see your name
          on it.
        </p>
      </Section>

      <Section title="Our responsibility to you" id="liability">
        <p>
          We are responsible for loss or damage you suffer that is a foreseeable result of our
          breaking these terms or failing to use reasonable care and skill. We are not responsible
          for loss that was not foreseeable, or for business losses: Forgeway is for personal
          learning. We do not limit our liability for death or personal injury caused by our
          negligence, for fraud, or for anything else the law does not allow us to limit, including
          your rights under the Consumer Rights Act 2015.
        </p>
      </Section>

      <Section title="Law and disputes" id="disputes">
        <p>
          If something goes wrong, please contact us first (see{' '}
          <Link to="/privacy" hash="complaints" className={LINK}>
            Complaints
          </Link>
          ); most problems are quickly put right. These terms are governed by the law of England and
          Wales. You can bring proceedings in the courts of England and Wales, or, if you live in
          Scotland or Northern Ireland, in the courts where you live.
        </p>
      </Section>

      <Section title="Contact">
        <p>
          Write to {hello} with any question, or to {contact} about your data.
        </p>
      </Section>
    </Page>
  );
}

/** The accessibility statement: voluntary, as evidence for the Equality Act 2010 duty. */
export function AccessibilityPage() {
  return (
    <Page
      title="Accessibility statement"
      summary="How accessible Forgeway is, what we know falls short, and how to tell us."
    >
      <Section title="Our aim">
        <p>
          We want everyone to be able to learn on Forgeway. We aim to meet the Web Content
          Accessibility Guidelines (WCAG) 2.2 at level AA, in both modes and both colour schemes.
        </p>
      </Section>

      <Section title="What you can do">
        <ul>
          <li>Use the site with a keyboard.</li>
          <li>Use a screen reader: pages have headings, landmarks and labelled controls.</li>
          <li>Choose a light or dark scheme, or follow your system&apos;s.</li>
          <li>Use it on a narrow screen.</li>
          <li>Resize the workspace columns with the keyboard as well as the mouse.</li>
        </ul>
      </Section>

      <Section title="What we know falls short">
        <ul>
          <li>
            The code editor is a rich text area; some screen readers announce its content and
            suggestions less clearly than a plain text field.
          </li>
          <li>
            The human check at sign-up comes from Cloudflare. If it stops you, email us and we will
            set up your account.
          </li>
        </ul>
      </Section>

      <Section title="How we test">
        <p>
          Our automated tests check the main pages in both modes for accessibility problems (with
          axe), and we try new features with a keyboard. This statement was prepared on{' '}
          {LEGAL_UPDATED}.
        </p>
      </Section>

      <Section title="Tell us">
        <p>
          If something is hard to use, or you need content in another format, email {hello}. We will
          reply within 5 working days. If you are not happy with our response, you can contact the{' '}
          <a href="https://www.equalityadvisoryservice.com/" className={LINK}>
            Equality Advisory and Support Service
          </a>
          .
        </p>
      </Section>
    </Page>
  );
}
