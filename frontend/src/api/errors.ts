import type { Lexicon } from '../theme/lexicon';

/** A talent named by a problem; `path` is the specialisation it belongs to, if any. */
export interface ProblemTalent {
  id: string;
  title: string;
  path: string | null;
}

/** A problem+json response (RFC 9457) from the API, surfaced as a readable message. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  /** Talents named by a problem that can be fixed by taking one (the reference-solution 403). */
  readonly talents: readonly ProblemTalent[];
  /** The daily attempt cap, on an `attempt-daily-cap` 429. */
  readonly limit: number | null;
  /** The grading minutes allowed per rolling 24 hours, on a `grading-budget` 429. */
  readonly budgetMinutes: number | null;

  constructor(
    status: number,
    code: string,
    detail: string,
    talents: readonly ProblemTalent[] = [],
    extensions: { limit?: number | null; budgetMinutes?: number | null } = {},
  ) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.talents = talents;
    this.limit = extensions.limit ?? null;
    this.budgetMinutes = extensions.budgetMinutes ?? null;
  }
}

const FALLBACK: Record<number, string> = {
  401: 'Your session has ended. Sign in to continue.',
  403: 'You are not allowed to do that.',
  404: 'That could not be found.',
  409: 'That conflicts with the current state. Refresh and try again.',
  429: 'Too many requests. Wait a moment and try again.',
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function integerOf(value: unknown): number | null {
  return typeof value === 'number' && Number.isInteger(value) ? value : null;
}

function talentsOf(value: unknown): ProblemTalent[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item: unknown) =>
    isRecord(item) && typeof item.id === 'string' && typeof item.title === 'string'
      ? [{ id: item.id, title: item.title, path: typeof item.path === 'string' ? item.path : null }]
      : [],
  );
}

/** Turn whatever the server (or a proxy in front of it) returned into an ApiError. */
export function toApiError(status: number, body: unknown): ApiError {
  if (isRecord(body)) {
    const { detail, code } = body;
    const codeText = typeof code === 'string' ? code : 'unknown';
    if (typeof detail === 'string' && detail !== '') {
      return new ApiError(status, codeText, detail, talentsOf(body.talents), {
        limit: integerOf(body.limit),
        budgetMinutes: integerOf(body.budget_minutes),
      });
    }
    if (Array.isArray(detail)) {
      const first: unknown = detail[0];
      if (isRecord(first) && typeof first.msg === 'string') {
        return new ApiError(status, 'invalid-input', first.msg);
      }
    }
  }
  const message = FALLBACK[status] ?? 'Something went wrong on our side. Try again shortly.';
  return new ApiError(status, 'unknown', message);
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) return 'Cannot reach the server. Check your connection.';
  return 'Something went wrong. Try again.';
}

/**
 * The message for a failed request, in the learner's mode. The server's problem codes get the
 * lexicon's wording; any other error keeps the server's own detail.
 */
export function problemMessage(error: unknown, lexicon: Lexicon): string {
  if (error instanceof ApiError) {
    const { problems } = lexicon;
    switch (error.code) {
      case 'plan-required':
        return problems.planRequired;
      case 'email-unverified':
        return problems.emailUnverified;
      case 'challenge-failed':
        return problems.challengeFailed;
      case 'attempt-in-flight':
        return problems.attemptInFlight;
      case 'rate-limited':
        return problems.rateLimited;
      case 'attempt-daily-cap':
        return problems.attemptDailyCap(error.limit);
      case 'grading-budget':
        return problems.gradingBudget(error.budgetMinutes);
      case 'busy':
        return problems.busy;
    }
  }
  return errorMessage(error);
}
