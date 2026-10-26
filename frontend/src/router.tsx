import type { QueryClient } from '@tanstack/react-query';
import {
  createRootRouteWithContext,
  createRoute,
  createRouter,
  lazyRouteComponent,
  redirect,
} from '@tanstack/react-router';

import { meQuery } from './api/hooks';
import { AppShell } from './components/AppShell';
import { AuthPage } from './features/auth/AuthPage';
import { ForgotPasswordPage } from './features/auth/ForgotPasswordPage';
import { ResetPasswordPage } from './features/auth/ResetPasswordPage';
import { VerifyEmailPage } from './features/auth/VerifyEmailPage';
import { PrivacyPage, TermsPage } from './features/legal/LegalPages';
import { MapPage } from './features/map/MapPage';
import { ProPage } from './features/pro/ProPage';
import { ProfilePage } from './features/profile/ProfilePage';
import { WhatsNewPage } from './features/releases/WhatsNewPage';

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
  beforeLoad: ({ context }) => requireSession(context.queryClient),
  component: MapPage,
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

const routeTree = rootRoute.addChildren([
  mapRoute,
  exerciseRoute,
  profileRoute,
  proRoute,
  whatsNewRoute,
  signInRoute,
  registerRoute,
  verifyEmailRoute,
  forgotPasswordRoute,
  resetPasswordRoute,
  privacyRoute,
  termsRoute,
]);

export function createAppRouter(queryClient: QueryClient) {
  return createRouter({ routeTree, context: { queryClient }, defaultPreload: 'intent' });
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
