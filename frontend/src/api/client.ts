import createClient, { type Middleware } from 'openapi-fetch';

import { toApiError } from './errors';
import type { paths } from './schema';

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

let csrfToken: string | null = null;

/** The token returned by /me, /login and /register; sent on every mutating request. */
export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

const csrf: Middleware = {
  onRequest({ request }) {
    if (csrfToken !== null && !SAFE_METHODS.has(request.method.toUpperCase())) {
      request.headers.set('X-CSRF-Token', csrfToken);
    }
    return request;
  },
};

/** A client bound to the current origin (the dev server and nginx both proxy /api). */
export function createApiClient(fetchImpl?: typeof fetch) {
  const client = createClient<paths>({
    baseUrl: globalThis.location.origin,
    // Resolved at call time so tests can substitute fetch after this module has loaded.
    fetch: fetchImpl ?? ((request) => globalThis.fetch(request)),
  });
  client.use(csrf);
  return client;
}

export const api = createApiClient();

interface Result<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Return the payload or throw an ApiError built from the problem response. */
export function unwrap<T>(result: Result<T>): T {
  if (result.error !== undefined || result.data === undefined) {
    throw toApiError(result.response.status, result.error);
  }
  return result.data;
}

/** For 204 responses: nothing to return, but still throw on a problem. */
export function ensureOk(result: Result<unknown>): void {
  if (result.error !== undefined) {
    throw toApiError(result.response.status, result.error);
  }
}
