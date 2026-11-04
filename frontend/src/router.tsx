import type { QueryClient } from '@tanstack/react-query';
import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  Link,
  lazyRouteComponent,
  redirect,
  type RouterHistory,
} from '@tanstack/react-router';

import { meQuery, useMe } from './api/hooks';
import { AppShell } from './components/AppShell';
import { AuthPage } from './features/auth/AuthPage';
import { ForgotPasswordPage } from './features/auth/ForgotPasswordPage';
import { ResetPasswordPage } from './features/auth/ResetPasswordPage';
import { VerifyEmailPage } from './features/auth/VerifyEmailPage';
import { LandingPage } from './features/landing/LandingPage';
import { AccessibilityPage, PrivacyPage, TermsPage } from './features/legal/LegalPages';
import { UnsubscribePage } from './features/legal/UnsubscribePage';
import { LiveModeGuidePage } from './features/livemode/LiveModeGuidePage';
import { ToolkitReferencePage } from './features/livemode/ToolkitReferencePage';
import { MapPage } from './features/map/MapPage';
import { CheckoutCancelledPage, CheckoutSuccessPage } from './features/pro/CheckoutReturn';
import { ProPage } from './features/pro/ProPage';
import { ProfilePage } from './features/profile/ProfilePage';
import { SecurityPathPage } from './features/security/SecurityPathPage';
import { WhatsNewPage } from './features/releases/WhatsNewPage';
import { PageHeader } from './theme/slots';
import { useLexicon } from './theme/useTheme';

interface RouterContext {
  queryClient: QueryClient;
}

const rootRoute = createRootRouteWithContext<RouterContext>()({ component: AppShell });

async function requireSession(queryClient: QueryClient): Promise<void> {
  if ((await queryClient.query(meQuery)) === null) {
    // eslint-disable-next-line @typescript-eslint/only-throw-error -- TanStack Router redirects are thrown
    throw redirect({ to: '/sign-in' });
  }
}

async function requireGuest(queryClient: QueryClient): Promise<void> {
  if ((await queryClient.query(meQuery)) !== null) {
    // eslint-disable-next-line @typescript-eslint/only-throw-error -- TanStack Router redirects are thrown
    throw redirect({ to: '/' });
  }
}

const mapRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  // `zone` selects a zone on the RPG world map; professional mode ignores it.
  validateSearch: (search: Record<string, unknown>): { zone?: string } =>
    typeof search.zone === 'string' || typeof search.zone === 'number'
      ? { zone: String(search.zone) }
      : {},
  // Signed in: the learner's map, as always. Signed out: the public landing page.
  beforeLoad: async ({ context }) => {
    await context.queryClient.query(meQuery);
  },
  component: function HomeRoute() {
    return useMe().data == null ? <LandingPage /> : <MapPage />;
  },
});

const exerciseRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/exercises/$exerciseId',
  // The workspace uses the full width, and fills the viewport from 1280px.
  staticData: { wide: true },
  beforeLoad: ({ context }) => requireSession(context.queryClient),
  // The workspace pulls in CodeMirror, so it loads on demand.
  component: lazyRouteComponent(
    () => import('./features/workspace/WorkspacePage'),
    'WorkspacePage',
  ),
});

const profileRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/profile',
  beforeLoad: ({ context }) => requireSession(context.queryClient),
  component: ProfilePage,
});

const proRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/pro',
  beforeLoad: ({ context }) => requireSession(context.queryClient),
  component: ProPage,
});

// Stripe Checkout returns here (docs/plans/billing.md).
const checkoutSuccessRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/pro/success',
  beforeLoad: ({ context }) => requireSession(context.queryClient),
  component: CheckoutSuccessPage,
});

const checkoutCancelledRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/pro/cancelled',
  beforeLoad: ({ context }) => requireSession(context.queryClient),
  component: CheckoutCancelledPage,
});

const whatsNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/whats-new',
  beforeLoad: ({ context }) => requireSession(context.queryClient),
  component: WhatsNewPage,
});

const signInRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/sign-in',
  beforeLoad: ({ context }) => requireGuest(context.queryClient),
  component: function SignInRoute() {
    return <AuthPage kind="sign-in" />;
  },
});

const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/register',
  beforeLoad: ({ context }) => requireGuest(context.queryClient),
  component: function RegisterRoute() {
    return <AuthPage kind="register" />;
  },
});

/** Emailed links carry a single `token` search parameter. */
function tokenSearch(search: Record<string, unknown>): { token?: string } {
  return typeof search.token === 'string' && search.token !== '' ? { token: search.token } : {};
}

// Signed in or not: the link may be opened in another browser.
const verifyEmailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/verify-email',
  validateSearch: tokenSearch,
  component: function VerifyEmailRoute() {
    return <VerifyEmailPage token={verifyEmailRoute.useSearch().token} />;
  },
});

const forgotPasswordRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/forgot-password',
  beforeLoad: ({ context }) => requireGuest(context.queryClient),
  component: ForgotPasswordPage,
});

const resetPasswordRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/reset-password',
  validateSearch: tokenSearch,
  component: function ResetPasswordRoute() {
    return <ResetPasswordPage token={resetPasswordRoute.useSearch().token} />;
  },
});

// Public, signed in or not: linked from the footer and the registration form.
const privacyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/privacy',
  component: PrivacyPage,
});

const termsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/terms',
  component: TermsPage,
});

const accessibilityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/accessibility',
  component: AccessibilityPage,
});

// Signed in or not: the link in a marketing email may be opened anywhere.
const unsubscribeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/unsubscribe',
  validateSearch: tokenSearch,
  component: function UnsubscribeRoute() {
    return <UnsubscribePage token={unsubscribeRoute.useSearch().token} />;
  },
});

// Public: linked from the Run locally panel, the downloaded README and the project briefs.
const liveModeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/live-mode',
  component: LiveModeGuidePage,
});

// Public: linked from the workspace, beside the editor.
const toolkitRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/toolkit',
  component: ToolkitReferencePage,
});

// Public: linked from the landing page and the syllabus.
const securityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/security',
  component: SecurityPathPage,
});

// Addresses people guess or remember from other sites.
const REDIRECTS = {
  '/home': '/',
  '/dashboard': '/',
  '/app': '/',
  '/login': '/sign-in',
  '/signin': '/sign-in',
  '/log-in': '/sign-in',
  '/signup': '/register',
  '/sign-up': '/register',
  '/join': '/register',
  '/subscribe': '/pro',
  '/upgrade': '/pro',
  '/account': '/profile',
  '/settings': '/profile',
  '/changelog': '/whats-new',
  '/releases': '/whats-new',
  '/privacy-policy': '/privacy',
  '/tos': '/terms',
  '/terms-of-service': '/terms',
  '/docs': '/toolkit',
} as const;

const redirectRoutes = Object.entries(REDIRECTS).map(([path, to]) =>
  createRoute({
    getParentRoute: () => rootRoute,
    path,
    beforeLoad: () => {
      // eslint-disable-next-line @typescript-eslint/only-throw-error -- TanStack Router redirects are thrown
      throw redirect({ to, replace: true });
    },
  }),
);

// `/` is the landing page only for visitors; this is it for everyone, so it can be linked to.
const welcomeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/welcome',
  component: LandingPage,
});

const pricingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/pricing',
  beforeLoad: () => {
    // eslint-disable-next-line @typescript-eslint/only-throw-error -- TanStack Router redirects are thrown
    throw redirect({ to: '/welcome', hash: 'landing-plans', replace: true });
  },
});

function NotFoundPage() {
  const copy = useLexicon();
  return (
    <div className="mx-auto max-w-page space-y-8 px-4 py-8 sm:px-6">
      <PageHeader title={copy.notFoundTitle} summary={copy.notFoundBody} />
      <Link to="/" className="text-accent-strong underline underline-offset-2">
        {copy.notFoundHome}
      </Link>
    </div>
  );
}

const routeTree = rootRoute.addChildren([
  mapRoute,
  exerciseRoute,
  profileRoute,
  proRoute,
  checkoutSuccessRoute,
  checkoutCancelledRoute,
  whatsNewRoute,
  signInRoute,
  registerRoute,
  verifyEmailRoute,
  forgotPasswordRoute,
  resetPasswordRoute,
  privacyRoute,
  termsRoute,
  accessibilityRoute,
  unsubscribeRoute,
  liveModeRoute,
  toolkitRoute,
  securityRoute,
  welcomeRoute,
  pricingRoute,
  ...redirectRoutes,
]);

/** `history` is for tests (a memory history); the app uses the browser's. */
export function createAppRouter(queryClient: QueryClient, history?: RouterHistory) {
  return createRouter({
    routeTree,
    context: { queryClient },
    defaultPreload: 'intent',
    defaultNotFoundComponent: NotFoundPage,
    history,
  });
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>;
  }
  interface StaticDataRouteOption {
    /** The page uses the full viewport width, so AppShell aligns its header to the same gutters. */
    wide?: boolean;
  }
}
