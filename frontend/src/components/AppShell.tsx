import { Link, Outlet, useMatches, useNavigate } from '@tanstack/react-router';
import { LogOut, Menu, Monitor, Moon, Sun, UserRound, X } from 'lucide-react';
import { useEffect, useRef, useState, type KeyboardEvent, type MouseEvent } from 'react';

import { useLearnerMap, useLogout, useMe } from '../api/hooks';
import { UnverifiedBanner } from '../features/auth/UnverifiedBanner';
import { WhatsNewLink } from '../features/releases/WhatsNewLink';
import type { ColourScheme, Mode } from '../api/types';
import { useTheme } from '../theme/useTheme';
import { Button } from './Button';
import { ProgressRule } from './ProgressRule';
import { Toggle } from './Toggle';

const MODE_OPTIONS = [
  { value: 'professional', label: 'Professional' },
  { value: 'rpg', label: 'RPG' },
] as const satisfies readonly { value: Mode; label: string }[];

const SCHEME_OPTIONS = [
  { value: 'system', label: 'System colour scheme', icon: Monitor },
  { value: 'light', label: 'Light colour scheme', icon: Sun },
  { value: 'dark', label: 'Dark colour scheme', icon: Moon },
] as const satisfies readonly { value: ColourScheme; label: string; icon: typeof Sun }[];

const MENU_ID = 'site-menu';
const FOOTER_LINK =
  'inline-flex min-h-11 items-center text-ink-secondary underline-offset-4 hover:text-ink hover:underline';

/**
 * The level and the rule towards the next one. On a phone it is compact (the XP figures are
 * kept for assistive technology only) so it shares the top row with the brand and the menu.
 */
function LevelSummary() {
  const { lexicon } = useTheme();
  const map = useLearnerMap();
  const level = map.data?.level;
  if (!level) return null;
  const span = level.next_level_at === null ? 0 : level.next_level_at - level.level_floor;
  return (
    <div
      className="flex min-w-0 flex-1 items-center gap-2 sm:max-w-sm sm:basis-0 sm:gap-3"
      aria-label="Your level"
    >
      <span className="tabular whitespace-nowrap font-semibold">
        {lexicon.levelLabel(level.level)}
      </span>
      <div className="min-w-0 flex-1">
        <ProgressRule
          value={span === 0 ? 1 : level.total_xp - level.level_floor}
          max={span === 0 ? 1 : span}
          label={`Experience towards ${lexicon.level} ${level.level + 1}`}
        />
      </div>
      <span className="tabular sr-only whitespace-nowrap text-sm text-ink-secondary sm:not-sr-only">
        {level.next_level_at === null
          ? lexicon.xpLabel(level.total_xp)
          : `${level.total_xp} / ${level.next_level_at} XP`}
      </span>
    </div>
  );
}

/**
 * Application chrome: skip link, header with level, navigation, toggles and sign out, then the
 * page, then a footer linking the privacy policy and terms (left out on wide routes). Below 640px the header keeps only the brand, a compact level and a menu button; the
 * navigation, both toggles and sign out sit in a disclosure the button opens (Escape closes it
 * and returns focus to the button). From 640px they are all shown inline, as before.
 */
export function AppShell() {
  const { mode, scheme, setMode, setScheme, lexicon } = useTheme();
  const me = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  const signedIn = me.data != null;
  // Wide routes (the workspace) span the viewport: the header drops its 1200px column to match,
  // and from 1280px the page fills the viewport below it (see `main[data-wide]` in index.css).
  const wide = useMatches({ select: (matches) => matches.some((match) => match.staticData.wide) });

  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (menuOpen)
      menu.current?.querySelector<HTMLElement>('a[href], button:not([disabled]), input')?.focus();
  }, [menuOpen]);

  const closeMenu = (returnFocus: boolean) => {
    setMenuOpen(false);
    if (returnFocus) menuButton.current?.focus();
  };
  const onMenuKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && menuOpen) {
      event.stopPropagation();
      closeMenu(true);
    }
  };
  // Following a link from the menu closes it; the new page takes focus as usual.
  const onMenuClick = (event: MouseEvent) => {
    if (event.target instanceof Element && event.target.closest('a')) closeMenu(false);
  };

  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-control focus:bg-raised focus:px-4 focus:py-2"
      >
        Skip to content
      </a>
      <header className="border-b border-line-subtle bg-raised" onKeyDown={onMenuKeyDown}>
        <div
          className={`mx-auto flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-3 sm:gap-x-6 sm:px-6 ${wide ? '' : 'max-w-page'}`}
        >
          <Link to="/" className="font-display text-xl font-semibold text-ink no-underline">
            {lexicon.appName}
          </Link>
          {signedIn && <LevelSummary />}
          <button
            ref={menuButton}
            type="button"
            className="ml-auto inline-flex min-h-11 items-center gap-2 rounded-control border border-line-strong px-3 font-ui text-base font-medium text-ink transition-colors duration-fast hover:bg-sunken sm:hidden"
            aria-expanded={menuOpen}
            aria-controls={MENU_ID}
            onClick={() => {
              setMenuOpen((open) => !open);
            }}
          >
            {menuOpen ? (
              <X aria-hidden="true" className="h-4 w-4" />
            ) : (
              <Menu aria-hidden="true" className="h-4 w-4" />
            )}
            Menu
          </button>
          <div
            ref={menu}
            id={MENU_ID}
            onClick={onMenuClick}
            className={`${menuOpen ? 'flex' : 'hidden'} basis-full flex-col items-start gap-3 border-t border-line-subtle pt-3 sm:contents`}
          >
            {signedIn && (
              <Link
                to="/profile"
                className="inline-flex min-h-11 items-center gap-2 text-ink no-underline hover:underline aria-[current=page]:underline aria-[current=page]:underline-offset-4"
              >
                <UserRound aria-hidden="true" className="h-4 w-4" />
                {lexicon.profile}
              </Link>
            )}
            {signedIn && <WhatsNewLink />}
            <div className="flex flex-wrap items-center gap-3 sm:ml-auto">
              <Toggle legend="Mode" value={mode} options={MODE_OPTIONS} onChange={setMode} />
              <Toggle
                legend="Colour scheme"
                value={scheme}
                options={SCHEME_OPTIONS}
                onChange={setScheme}
              />
              {signedIn && (
                // Its own row on a phone, its text aligned with the links above.
                <div className="basis-full sm:basis-auto">
                  <Button
                    variant="quiet"
                    className="-ml-4 sm:ml-0"
                    loading={logout.isPending}
                    onClick={() => {
                      logout.mutate(undefined, {
                        onSuccess: () => {
                          setMenuOpen(false);
                          void navigate({ to: '/sign-in' });
                        },
                      });
                    }}
                  >
                    <LogOut aria-hidden="true" className="h-4 w-4" />
                    Sign out
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>
      <UnverifiedBanner />
      <main
        id="main"
        tabIndex={-1}
        data-wide={wide || undefined}
        className={`outline-none ${wide ? 'xl:min-h-0 xl:flex-1' : ''}`}
      >
        <Outlet />
      </main>
      {/* The workspace fills the viewport, so it leaves the footer out. */}
      {!wide && (
        <footer className="border-t border-line-subtle">
          <nav
            aria-label="Site"
            className="mx-auto flex max-w-page flex-wrap gap-x-6 gap-y-2 px-4 py-6 text-sm sm:px-6"
          >
            <Link to="/privacy" className={FOOTER_LINK}>
              Privacy
            </Link>
            <Link to="/terms" className={FOOTER_LINK}>
              Terms
            </Link>
          </nav>
        </footer>
      )}
    </>
  );
}
