import {
  queryOptions,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query';

import { api, ensureOk, setCsrfToken, unwrap } from './client';
import { ApiError } from './errors';
import type {
  AttemptDetail,
  Certificate,
  ColourScheme,
  ExerciseDetail,
  Me,
  Mode,
  ReleaseList,
  TalentTree,
} from './types';

export const queryKeys = {
  me: ['me'] as const,
  map: ['map'] as const,
  exercise: (id: string) => ['exercise', id] as const,
  rpgFlavour: ['rpg-flavour'] as const,
  pathProfile: ['path-profile'] as const,
  talents: ['talents'] as const,
  badges: ['badges'] as const,
  certificates: ['certificates'] as const,
  referenceSolutions: ['reference-solution'] as const,
  referenceSolution: (id: string) => ['reference-solution', id] as const,
  config: ['config'] as const,
  waitlist: ['pro-waitlist'] as const,
  releases: ['releases'] as const,
};

/** The signed-in learner, or null when there is no session. */
export const meQuery = queryOptions({
  queryKey: queryKeys.me,
  queryFn: async (): Promise<Me | null> => {
    const result = await api.GET('/api/auth/me');
    if (result.response.status === 401) {
      setCsrfToken(null);
      return null;
    }
    const me = unwrap(result);
    setCsrfToken(me.csrf_token);
    return me;
  },
  staleTime: 'static',
  retry: false,
});

export function useMe() {
  return useQuery(meQuery);
}

function adoptSession(client: QueryClient, me: Me): void {
  setCsrfToken(me.csrf_token);
  client.setQueryData(queryKeys.me, me);
  void client.invalidateQueries({ queryKey: queryKeys.map });
}

export function useRegister() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      email: string;
      password: string;
      display_name: string;
      time_zone?: string;
      mode?: Mode;
      colour_scheme?: ColourScheme;
      turnstile_token?: string;
    }) => unwrap(await api.POST('/api/auth/register', { body })),
    onSuccess: (me) => {
      adoptSession(client, me);
    },
  });
}

export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { email: string; password: string }) =>
      unwrap(await api.POST('/api/auth/login', { body })),
    onSuccess: (me) => {
      adoptSession(client, me);
    },
  });
}

/** Public configuration: the Turnstile site key, or null when the human check is off. */
export function usePublicConfig() {
  return useQuery({
    queryKey: queryKeys.config,
    queryFn: async () => unwrap(await api.GET('/api/config')),
    staleTime: 'static',
  });
}

/** Follow a verification link. Signed in or not; a signed-in learner's banner then goes. */
export function useVerifyEmail() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (token: string) => {
      ensureOk(await api.POST('/api/auth/verify-email', { body: { token } }));
    },
    onSuccess: async () => {
      // `me` is static, which invalidateQueries and refetchQueries both skip, and a fetch that
      // started before the link was followed would answer "unverified": drop it, fetch afresh.
      await client.cancelQueries({ queryKey: queryKeys.me });
      await client.query({ ...meQuery, staleTime: 0 });
    },
  });
}

export function useResendVerification() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/auth/verify-email/resend')),
    onSuccess: (me) => {
      client.setQueryData(queryKeys.me, me);
    },
  });
}

/** Always answers the same, whether or not the address has an account. */
export function useRequestPasswordReset() {
  return useMutation({
    mutationFn: async (email: string) => {
      ensureOk(await api.POST('/api/auth/password-reset', { body: { email } }));
    },
  });
}

/** Set a new password from a reset link. Every session ends, this one included. */
/** Whether a reset link still works, asked once when the page opens (the token is not used). */
export function usePasswordResetCheck(token: string | undefined) {
  return useQuery({
    queryKey: ['password-reset-check', token],
    queryFn: async () => {
      ensureOk(await api.POST('/api/auth/password-reset/check', { body: { token: token ?? '' } }));
      return true;
    },
    enabled: token !== undefined,
    retry: false,
    staleTime: Infinity,
  });
}

export function useConfirmPasswordReset() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { token: string; password: string }) => {
      ensureOk(await api.POST('/api/auth/password-reset/confirm', { body }));
    },
    onSuccess: () => {
      setCsrfToken(null);
      client.clear();
      client.setQueryData(queryKeys.me, null);
    },
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      ensureOk(await api.POST('/api/auth/logout'));
    },
    onSuccess: () => {
      setCsrfToken(null);
      client.clear();
      client.setQueryData(queryKeys.me, null);
    },
  });
}

/** Fetch everything held about the learner and save it as a JSON file. */
export function useExportAccount() {
  return useMutation({
    mutationFn: async () => {
      const data = unwrap(await api.GET('/api/account/export'));
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `forgeway-data-${data.exported_at.slice(0, 10)}.json`;
      document.body.append(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    },
  });
}

/** Delete the account (the current password confirms it). Every session ends, this one too. */
export function useDeleteAccount() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (password: string) => {
      ensureOk(await api.POST('/api/account/delete', { body: { password } }));
    },
    onSuccess: () => {
      setCsrfToken(null);
      client.clear();
      client.setQueryData(queryKeys.me, null);
    },
  });
}

export function useUpdateProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { mode?: Mode; colour_scheme?: ColourScheme }) =>
      unwrap(await api.PATCH('/api/auth/profile', { body })),
    onSuccess: (me) => {
      client.setQueryData(queryKeys.me, me);
    },
  });
}

export function useLearnerMap(enabled = true) {
  return useQuery({
    queryKey: queryKeys.map,
    queryFn: async () => unwrap(await api.GET('/api/map')),
    enabled,
  });
}

/** Zone and quest names for RPG mode. Public and effectively static, so fetched once. */
export const rpgFlavourQuery = queryOptions({
  queryKey: queryKeys.rpgFlavour,
  queryFn: async () => unwrap(await api.GET('/api/themes/rpg/flavour')),
  staleTime: 60 * 60 * 1000,
  retry: 1,
});

export function useExercise(exerciseId: string) {
  return useQuery({
    queryKey: queryKeys.exercise(exerciseId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/exercises/{exercise_id}', {
          params: { path: { exercise_id: exerciseId } },
        }),
      ),
    refetchOnWindowFocus: false,
    retry: (count, error) => !(error instanceof ApiError) && count < 2,
  });
}

export async function saveDraft(exerciseId: string, files: Record<string, string>): Promise<void> {
  ensureOk(
    await api.PUT('/api/exercises/{exercise_id}/draft', {
      params: { path: { exercise_id: exerciseId } },
      body: { files },
    }),
  );
}

/** Discard the draft and any carried files; the answer is the exercise on its starter files. */
export function useResetToStarter(exerciseId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.DELETE('/api/exercises/{exercise_id}/draft', {
          params: { path: { exercise_id: exerciseId } },
        }),
      ),
    onSuccess: (exercise) => {
      client.setQueryData(queryKeys.exercise(exerciseId), exercise);
    },
  });
}

export function useSubmitAttempt(exerciseId: string) {
  return useMutation({
    mutationFn: async (files: Record<string, string>) =>
      unwrap(
        await api.POST('/api/exercises/{exercise_id}/attempts', {
          params: { path: { exercise_id: exerciseId } },
          body: { files },
        }),
      ),
  });
}

export function useRevealHint(exerciseId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST('/api/exercises/{exercise_id}/hints', {
          params: { path: { exercise_id: exerciseId } },
        }),
      ),
    onSuccess: (hints) => {
      client.setQueryData<ExerciseDetail>(
        queryKeys.exercise(exerciseId),
        (previous) => previous && { ...previous, ...hints },
      );
    },
  });
}

export async function fetchAttempt(attemptId: string): Promise<AttemptDetail> {
  return unwrap(
    await api.GET('/api/attempts/{attempt_id}', { params: { path: { attempt_id: attemptId } } }),
  );
}

export function usePathProfile() {
  return useQuery({
    queryKey: queryKeys.pathProfile,
    queryFn: async () => unwrap(await api.GET('/api/profile')),
  });
}

/** Everything that depends on the learner's build, after the path, zone or talents change. */
function refreshBuild(client: QueryClient): void {
  for (const queryKey of [queryKeys.pathProfile, queryKeys.talents, queryKeys.referenceSolutions]) {
    void client.invalidateQueries({ queryKey });
  }
}

/** Choose a path or change the time zone. The response lists any talents the change refunded. */
export function useUpdatePathProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async (body: { path?: string; time_zone?: string }) =>
      unwrap(await api.PUT('/api/profile', { body })),
    onSuccess: (profile) => {
      client.setQueryData(queryKeys.pathProfile, profile);
      refreshBuild(client);
      // "Today", and so the streak, depends on the zone.
      void client.invalidateQueries({ queryKey: queryKeys.map });
    },
  });
}

export function useTalents() {
  return useQuery({
    queryKey: queryKeys.talents,
    queryFn: async () => unwrap(await api.GET('/api/talents')),
  });
}

/** Allocate, deallocate or respec: each answers with the new tree. */
export function useTalentActions() {
  const client = useQueryClient();
  const done = (tree: TalentTree) => {
    client.setQueryData(queryKeys.talents, tree);
    refreshBuild(client);
  };
  const allocate = useMutation({
    mutationFn: async (nodeId: string) =>
      unwrap(
        await api.POST('/api/talents/{node_id}/allocation', {
          params: { path: { node_id: nodeId } },
        }),
      ),
    onSuccess: done,
  });
  const deallocate = useMutation({
    mutationFn: async (nodeId: string) =>
      unwrap(
        await api.DELETE('/api/talents/{node_id}/allocation', {
          params: { path: { node_id: nodeId } },
        }),
      ),
    onSuccess: done,
  });
  const respec = useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/talents/respec')),
    onSuccess: done,
  });
  return { allocate, deallocate, respec };
}

export function useBadges() {
  return useQuery({
    queryKey: queryKeys.badges,
    queryFn: async () => unwrap(await api.GET('/api/badges')),
  });
}

/**
 * The reference solution. It is only fetched once the exercise is passed (`enabled`); a 403 is
 * an answer, not a failure, so it is not retried.
 */
export function useReferenceSolution(exerciseId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.referenceSolution(exerciseId),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/exercises/{exercise_id}/reference-solution', {
          params: { path: { exercise_id: exerciseId } },
        }),
      ),
    enabled,
    retry: false,
    refetchOnWindowFocus: false,
  });
}

export function useCertificates() {
  return useQuery({
    queryKey: queryKeys.certificates,
    queryFn: async () => unwrap(await api.GET('/api/certificates')),
  });
}

/** Publish, unpublish or rename one certificate; the answer replaces it in the cached list. */
export function useUpdateCertificate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      ...body
    }: {
      id: string;
      is_public?: boolean;
      recipient_name?: string;
    }) =>
      unwrap(
        await api.PATCH('/api/certificates/{certificate_id}', {
          params: { path: { certificate_id: id } },
          body,
        }),
      ),
    onSuccess: (updated) => {
      client.setQueryData<{ certificates: Certificate[] }>(
        queryKeys.certificates,
        (previous) =>
          previous && {
            certificates: previous.certificates.map((c) => (c.id === updated.id ? updated : c)),
          },
      );
    },
  });
}

/** Whether the learner has joined the Forgeway Pro waitlist. */
export function useWaitlist() {
  return useQuery({
    queryKey: queryKeys.waitlist,
    queryFn: async () => unwrap(await api.GET('/api/pro/waitlist')),
  });
}

/** Join the waitlist. Idempotent: joining twice keeps the first entry. Nothing is charged. */
export function useJoinWaitlist() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/pro/waitlist', { body: { plan: 'pro' } })),
    onSuccess: (status) => {
      client.setQueryData(queryKeys.waitlist, status);
    },
  });
}

/** Content releases, newest first, with whether one is unread. */
export function useReleases(enabled = true) {
  return useQuery({
    queryKey: queryKeys.releases,
    queryFn: async () => unwrap(await api.GET('/api/releases')),
    enabled,
  });
}

/** Mark the newest release as seen, which clears the unread marker. */
export function useMarkReleasesSeen() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST('/api/releases/seen')),
    onSuccess: (releases: ReleaseList) => {
      client.setQueryData(queryKeys.releases, releases);
    },
  });
}
