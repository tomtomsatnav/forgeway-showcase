import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { newQueryClient } from '../test/render';
import { ThemeProvider } from './ThemeProvider';
import { useTheme } from './useTheme';

function Probe() {
  const { mode, scheme, setMode, setScheme, lexicon } = useTheme();
  return (
    <>
      <p>{`${mode}/${scheme}/${lexicon.exercise}`}</p>
      <button
        onClick={() => {
          setMode('rpg');
        }}
      >
        rpg
      </button>
      <button
        onClick={() => {
          setScheme('dark');
        }}
      >
        dark
      </button>
    </>
  );
}

function mountWith(fetchMock: typeof fetch) {
  vi.stubGlobal('fetch', fetchMock);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ThemeProvider>
        <Probe />
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('ThemeProvider', () => {
  beforeEach(() => {
    delete document.documentElement.dataset.mode;
    delete document.documentElement.dataset.scheme;
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sets data-mode and data-scheme on <html> and remembers them locally before sign-in', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(json({ detail: 'Sign in', code: 'unauthenticated' }, 401)),
    );
    mountWith(fetchMock);
    const user = userEvent.setup();

    await user.click(screen.getByRole('button', { name: 'rpg' }));
    await user.click(screen.getByRole('button', { name: 'dark' }));

    expect(document.documentElement.dataset.mode).toBe('rpg');
    expect(document.documentElement.dataset.scheme).toBe('dark');
    expect(screen.getByText('rpg/dark/quest')).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem('lattice.theme') ?? '{}')).toEqual({
      mode: 'rpg',
      scheme: 'dark',
    });
  });

  it('adopts the saved profile on sign-in and persists changes with the CSRF header', async () => {
    const me = {
      id: 'u1',
      email: 'a@example.com',
      display_name: 'A',
      csrf_token: 'csrf-123',
      profile: { mode: 'professional', colour_scheme: 'light' },
    };
    const fetchMock = vi.fn((request: Request) =>
      Promise.resolve(
        request.method === 'PATCH'
          ? json({ ...me, profile: { mode: 'rpg', colour_scheme: 'light' } })
          : json(me),
      ),
    );
    mountWith(fetchMock as unknown as typeof fetch);
    await screen.findByText('professional/light/exercise');
    expect(document.documentElement.dataset.scheme).toBe('light');

    await userEvent.setup().click(screen.getByRole('button', { name: 'rpg' }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([request]) => request.method === 'PATCH')).toBe(true);
    });
    const patch = fetchMock.mock.calls
      .map(([request]) => request)
      .find((request) => request.method === 'PATCH');
    expect(patch?.headers.get('X-CSRF-Token')).toBe('csrf-123');
    expect(await patch?.clone().json()).toEqual({ mode: 'rpg' });
    expect(document.documentElement.dataset.mode).toBe('rpg');
  });
  it('keeps a choice made before the profile loads, and saves it', async () => {
    const me = {
      id: 'u1',
      email: 'a@example.com',
      display_name: 'A',
      csrf_token: 'csrf-123',
      profile: { mode: 'professional', colour_scheme: 'light' },
    };
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const fetchMock = vi.fn(async (request: Request) => {
      if (request.method === 'GET') await gate;
      return json(me);
    });
    mountWith(fetchMock as unknown as typeof fetch);

    // The toggles are usable while /me is still in flight.
    await userEvent.setup().click(screen.getByRole('button', { name: 'rpg' }));
    release();

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([request]) => request.method === 'PATCH')).toBe(true);
    });
    const patch = fetchMock.mock.calls
      .map(([request]) => request)
      .find((request) => request.method === 'PATCH');
    expect(await patch?.clone().json()).toEqual({ mode: 'rpg' });
    // The saved scheme is adopted; the explicit mode is not reverted to "professional".
    expect(await screen.findByText('rpg/light/quest')).toBeInTheDocument();
    expect(document.documentElement.dataset.mode).toBe('rpg');
  });
});
