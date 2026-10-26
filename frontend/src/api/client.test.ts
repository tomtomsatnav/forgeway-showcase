import { afterEach, describe, expect, it, vi } from 'vitest';

import { createApiClient, ensureOk, setCsrfToken, unwrap } from './client';
import { ApiError } from './errors';

function mockFetch(response: Response) {
  return vi.fn<(request: Request) => Promise<Response>>(() => Promise.resolve(response.clone()));
}

const problem = (status: number, detail: string, code: string) =>
  new Response(JSON.stringify({ type: 'about:blank', title: 'x', status, detail, code }), {
    status,
    headers: { 'content-type': 'application/problem+json' },
  });

describe('API client', () => {
  afterEach(() => {
    setCsrfToken(null);
  });

  it('sends the CSRF token on mutations but not on reads', async () => {
    const fetchMock = mockFetch(new Response(null, { status: 204 }));
    const client = createApiClient(fetchMock as unknown as typeof fetch);
    setCsrfToken('token-abc');

    await client.PUT('/api/exercises/{exercise_id}/draft', {
      params: { path: { exercise_id: 'x' } },
      body: { files: { 'a.py': '1' } },
    });
    await client.POST('/api/auth/logout');
    await client.PATCH('/api/auth/profile', { body: { mode: 'rpg' } });
    await client.GET('/api/map');

    const sent = fetchMock.mock.calls.map(([request]) => request);
    expect(sent.map((request) => request.method)).toEqual(['PUT', 'POST', 'PATCH', 'GET']);
    expect(sent.slice(0, 3).map((request) => request.headers.get('X-CSRF-Token'))).toEqual([
      'token-abc',
      'token-abc',
      'token-abc',
    ]);
    expect(sent[3]?.headers.has('X-CSRF-Token')).toBe(false);
  });

  it('omits the header when there is no session token', async () => {
    const fetchMock = mockFetch(new Response(null, { status: 204 }));
    await createApiClient(fetchMock as unknown as typeof fetch).POST('/api/auth/logout');

    expect(fetchMock.mock.calls[0]?.[0].headers.has('X-CSRF-Token')).toBe(false);
  });

  it('turns a problem+json response into a readable ApiError', async () => {
    const fetchMock = mockFetch(problem(429, 'Slow down: 5 attempts per minute.', 'rate-limited'));
    const client = createApiClient(fetchMock as unknown as typeof fetch);
    const result = await client.POST('/api/exercises/{exercise_id}/attempts', {
      params: { path: { exercise_id: 'x' } },
      body: { files: {} },
    });

    const error = (() => {
      try {
        unwrap(result);
      } catch (caught) {
        return caught;
      }
    })();
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 429,
      code: 'rate-limited',
      message: 'Slow down: 5 attempts per minute.',
    });
  });

  it('falls back to plain wording when a proxy returns something that is not a problem', async () => {
    const fetchMock = mockFetch(new Response('<html>Bad gateway</html>', { status: 502 }));
    const result = await createApiClient(fetchMock as unknown as typeof fetch).GET('/api/map');

    expect(() => unwrap(result)).toThrow(/Something went wrong on our side/);
  });

  it('treats an empty success as success and an empty failure as failure', async () => {
    const ok = await createApiClient(
      mockFetch(new Response(null, { status: 204 })) as unknown as typeof fetch,
    ).POST('/api/auth/logout');
    expect(() => {
      ensureOk(ok);
    }).not.toThrow();

    const failed = await createApiClient(
      mockFetch(problem(409, 'Already queued.', 'conflict')) as unknown as typeof fetch,
    ).POST('/api/auth/logout');
    expect(() => {
      ensureOk(failed);
    }).toThrow('Already queued.');
  });
});
