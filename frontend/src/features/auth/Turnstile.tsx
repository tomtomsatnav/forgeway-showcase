import { useEffect, useRef } from 'react';

import { useLexicon } from '../../theme/useTheme';

const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

interface TurnstileApi {
  render: (
    element: HTMLElement,
    options: {
      sitekey: string;
      callback: (token: string) => void;
      'expired-callback': () => void;
      'error-callback': () => void;
      theme?: 'auto' | 'light' | 'dark';
    },
  ) => string;
  remove: (widgetId: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

let loading: Promise<TurnstileApi> | null = null;

/** Load Cloudflare's script once, however many widgets mount. */
function loadTurnstile(): Promise<TurnstileApi> {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  loading ??= new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = SCRIPT_SRC;
    script.async = true;
    script.onload = () => {
      if (window.turnstile) resolve(window.turnstile);
      else reject(new Error('Turnstile did not load'));
    };
    script.onerror = () => {
      loading = null;
      reject(new Error('Turnstile did not load'));
    };
    document.head.appendChild(script);
  });
  return loading;
}

/**
 * Cloudflare Turnstile, rendered only when the API reports a site key. `onToken` receives the
 * widget's `cf-turnstile-response` (or null when it expires or fails), which the form sends.
 */
export function Turnstile({
  siteKey,
  onToken,
}: {
  siteKey: string;
  onToken: (token: string | null) => void;
}) {
  const lexicon = useLexicon();
  const container = useRef<HTMLDivElement>(null);
  const callback = useRef(onToken);
  useEffect(() => {
    callback.current = onToken;
  });

  useEffect(() => {
    let widgetId: string | null = null;
    let cancelled = false;
    loadTurnstile()
      .then((api) => {
        if (cancelled || container.current === null) return;
        widgetId = api.render(container.current, {
          sitekey: siteKey,
          theme: 'auto',
          callback: (token) => {
            callback.current(token);
          },
          'expired-callback': () => {
            callback.current(null);
          },
          'error-callback': () => {
            callback.current(null);
          },
        });
      })
      .catch(() => {
        callback.current(null);
      });
    return () => {
      cancelled = true;
      if (widgetId !== null) window.turnstile?.remove(widgetId);
    };
  }, [siteKey]);

  return (
    <div role="group" aria-labelledby="turnstile-label" className="space-y-1">
      <p id="turnstile-label" className="m-0 text-sm font-medium">
        {lexicon.humanCheckTitle}
      </p>
      <p className="m-0 text-sm text-ink-muted">{lexicon.humanCheckBody}</p>
      <div ref={container} data-testid="turnstile" />
    </div>
  );
}
