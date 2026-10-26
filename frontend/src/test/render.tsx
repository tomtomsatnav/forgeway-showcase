import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from '@tanstack/react-router';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';

import { queryKeys } from '../api/hooks';
import type { Mode, ThemeFlavour } from '../api/types';
import { LEXICONS } from '../theme/lexicon';
import { ThemeContext } from '../theme/useTheme';

/** Provide a mode's lexicon without the full ThemeProvider (no network, no <html> side effects). */
export function withMode(mode: Mode, children: ReactElement): ReactElement {
  return (
    <ThemeContext.Provider
      value={{
        mode,
        scheme: 'light',
        resolvedScheme: 'light',
        lexicon: LEXICONS[mode],
        setMode: () => undefined,
        setScheme: () => undefined,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export const EMPTY_FLAVOUR: ThemeFlavour = { branches: {}, quests: {}, paths: {}, bosses: {} };

/** Render inside a memory router so <Link> resolves real hrefs. Await the returned promise. */
export async function renderInRouter(
  ui: ReactElement,
  flavour: ThemeFlavour = EMPTY_FLAVOUR,
  initialEntry = '/',
) {
  const client = newQueryClient();
  client.setQueryData(queryKeys.rpgFlavour, flavour);
  const root = createRootRoute({
    component: () => <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  });
  const exercise = createRoute({
    getParentRoute: () => root,
    path: '/exercises/$exerciseId',
    component: () => null,
  });
  const profile = createRoute({
    getParentRoute: () => root,
    path: '/profile',
    component: () => null,
  });
  const pages = ['/pro', '/whats-new', '/privacy', '/terms', '/sign-in'].map((path) =>
    createRoute({ getParentRoute: () => root, path, component: () => null }),
  );
  const router = createRouter({
    routeTree: root.addChildren([exercise, profile, ...pages]),
    history: createMemoryHistory({ initialEntries: [initialEntry] }),
  });
  const result = render(<RouterProvider router={router} />);
  await router.load();
  return { ...result, router };
}

export function newQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

export function QueryWrapper({
  client,
  children,
}: {
  client: QueryClient;
  children: ReactElement;
}) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
