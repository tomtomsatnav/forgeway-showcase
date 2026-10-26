import { HighlightStyle, syntaxHighlighting } from '@codemirror/language';
import { EditorView } from '@codemirror/view';
import { tags } from '@lezer/highlight';
import CodeMirror from '@uiw/react-codemirror';
import { ChevronRight } from 'lucide-react';
import { useId, useMemo, useRef, type KeyboardEvent } from 'react';

import { useLexicon } from '../theme/useTheme';
import { editorShortcuts, pythonEditorSetup } from './editor/setup';

/** A translucent accent wash, so text and the active line show through the selection. */
const selection = 'color-mix(in srgb, var(--accent) 30%, transparent)';

/**
 * The editor theme is written against the semantic CSS variables, so a mode or scheme change
 * restyles it live with no extension swap. That covers CodeMirror's own chrome too: tooltips,
 * the completion list, the find and replace panel, bracket matches and indent markers.
 */
const chrome = EditorView.theme({
  '&': {
    backgroundColor: 'var(--surface-raised)',
    color: 'var(--text-primary)',
    fontSize: '14px',
    height: '100%',
  },
  '&.cm-focused': { outline: '2px solid var(--focus-ring)', outlineOffset: '-2px' },
  '.cm-scroller': { fontFamily: 'var(--font-mono)', lineHeight: '1.6', overflow: 'auto' },
  '.cm-content': { caretColor: 'var(--accent-strong)', padding: '12px 0' },
  '.cm-cursor, .cm-dropCursor': { borderLeftColor: 'var(--accent-strong)' },
  '.cm-gutters': {
    backgroundColor: 'var(--surface-sunken)',
    color: 'var(--text-muted)',
    border: 'none',
    borderRight: '1px solid var(--border-subtle)',
  },
  // Translucent, so the selection layer beneath the line stays visible on it.
  '.cm-activeLine': { backgroundColor: 'color-mix(in srgb, var(--accent-soft) 60%, transparent)' },
  '.cm-activeLineGutter': { backgroundColor: 'var(--accent-soft)', color: 'var(--text-primary)' },
  '&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection':
    { backgroundColor: selection },
  '.cm-selectionMatch': { backgroundColor: 'var(--warning-soft)' },
  '&.cm-focused .cm-matchingBracket, .cm-matchingBracket': {
    outline: '1px solid var(--border-strong)',
    backgroundColor: 'var(--success-soft)',
    color: 'inherit',
  },
  '&.cm-focused .cm-nonmatchingBracket, .cm-nonmatchingBracket': {
    backgroundColor: 'var(--danger-soft)',
    color: 'var(--danger)',
  },
  '.cm-foldGutter .cm-gutterElement': { color: 'var(--text-muted)', cursor: 'pointer' },
  '.cm-foldPlaceholder': {
    backgroundColor: 'var(--surface-sunken)',
    border: '1px solid var(--border-strong)',
    color: 'var(--text-secondary)',
  },
  '.cm-searchMatch': {
    backgroundColor: 'var(--warning-soft)',
    outline: '1px solid var(--border-strong)',
  },
  '.cm-searchMatch.cm-searchMatch-selected': { backgroundColor: 'var(--accent-soft)' },

  // Tooltips: hovers, the completion list and its info panel.
  '.cm-tooltip': {
    backgroundColor: 'var(--surface-raised)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-strong)',
    borderRadius: 'var(--radius-control)',
    boxShadow: 'var(--shadow-raised)',
    fontFamily: 'var(--font-ui)',
    fontSize: '13px',
  },
  '.cm-tooltip.cm-tooltip-autocomplete > ul': { fontFamily: 'var(--font-mono)', maxHeight: '16em' },
  '.cm-tooltip.cm-tooltip-autocomplete > ul > li': { padding: '2px 8px' },
  '.cm-tooltip-autocomplete ul li[aria-selected]': {
    backgroundColor: 'var(--accent)',
    color: 'var(--text-on-accent)',
  },
  '.cm-completionDetail': { color: 'var(--text-muted)', fontStyle: 'normal', marginLeft: '1em' },
  '.cm-tooltip-autocomplete ul li[aria-selected] .cm-completionDetail': { color: 'inherit' },
  '.cm-completionMatchedText': { textDecoration: 'none', fontWeight: '700' },
  '.cm-completionIcon': { opacity: '1' },
  '.cm-tooltip.cm-completionInfo': { padding: '8px 10px', maxWidth: '28rem' },
  '.cm-kit-doc': { maxWidth: '28rem', padding: '8px 10px' },
  '.cm-completionInfo .cm-kit-doc': { padding: '0' },
  '.cm-kit-signature': {
    margin: '0',
    fontFamily: 'var(--font-mono)',
    fontSize: '12px',
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere',
  },
  '.cm-kit-summary': { margin: '6px 0 0', color: 'var(--text-secondary)', lineHeight: '1.5' },
  '.cm-kit-summary code': { fontFamily: 'var(--font-mono)', fontSize: '12px' },

  // The find and replace panel.
  '.cm-panels': { backgroundColor: 'var(--surface-sunken)', color: 'var(--text-primary)' },
  '.cm-panels.cm-panels-bottom': { borderTop: '1px solid var(--border-subtle)' },
  '.cm-panel.cm-search': { fontFamily: 'var(--font-ui)', fontSize: '13px', padding: '6px 8px' },
  '.cm-panel.cm-search label': { color: 'var(--text-secondary)', fontSize: '13px' },
  '.cm-textfield': {
    backgroundColor: 'var(--surface-raised)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-strong)',
    borderRadius: 'var(--radius-control)',
    fontFamily: 'var(--font-mono)',
    fontSize: '13px',
  },
  '.cm-button': {
    backgroundColor: 'var(--surface-raised)',
    backgroundImage: 'none',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-strong)',
    borderRadius: 'var(--radius-control)',
    fontSize: '13px',
  },
  '.cm-button:active': { backgroundImage: 'none', backgroundColor: 'var(--accent-soft)' },
  '.cm-panel.cm-search [name=close]': { color: 'var(--text-muted)', fontSize: '18px' },
  '.cm-panel.cm-search :focus-visible': {
    outline: '2px solid var(--focus-ring)',
    outlineOffset: '1px',
  },
});

const highlight = syntaxHighlighting(
  HighlightStyle.define([
    {
      tag: [tags.keyword, tags.operatorKeyword, tags.controlKeyword],
      color: 'var(--accent-strong)',
      fontWeight: '500',
    },
    { tag: [tags.string, tags.special(tags.string)], color: 'var(--success)' },
    { tag: [tags.number, tags.bool, tags.null], color: 'var(--warning)' },
    { tag: [tags.comment, tags.docString], color: 'var(--text-muted)', fontStyle: 'italic' },
    {
      tag: [tags.function(tags.variableName), tags.definition(tags.variableName)],
      color: 'var(--tier-advanced)',
    },
    { tag: [tags.className, tags.typeName], color: 'var(--tier-intermediate)' },
  ]),
);

const setup = pythonEditorSetup();

interface CodeEditorProps {
  /** Editable files, by path. */
  files: Record<string, string>;
  paths: readonly string[];
  activePath: string;
  onActivePathChange: (path: string) => void;
  onChange: (path: string, value: string) => void;
  disabled?: boolean;
}

export function CodeEditor({
  files,
  paths,
  activePath,
  onActivePathChange,
  onChange,
  disabled = false,
}: CodeEditorProps) {
  const lexicon = useLexicon();
  const panelId = useId();
  const tabRefs = useRef(new Map<string, HTMLButtonElement>());
  const label = `Code editor for ${activePath}`;

  const extensions = useMemo(
    () => [
      setup,
      chrome,
      highlight,
      EditorView.contentAttributes.of({ 'aria-label': label, tabindex: '0' }),
    ],
    [label],
  );

  const onTabKeyDown = (event: KeyboardEvent, index: number) => {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    if (step === 0) return;
    event.preventDefault();
    const next = paths[(index + step + paths.length) % paths.length];
    if (next !== undefined) {
      onActivePathChange(next);
      tabRefs.current.get(next)?.focus();
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-panel border border-line-strong bg-raised">
      <div
        role="tablist"
        aria-label="Files"
        className="flex shrink-0 gap-1 overflow-x-auto border-b border-line-subtle bg-sunken px-2 pt-2"
      >
        {paths.map((path, index) => {
          const selected = path === activePath;
          return (
            <button
              key={path}
              ref={(node) => {
                if (node) tabRefs.current.set(path, node);
                else tabRefs.current.delete(path);
              }}
              role="tab"
              type="button"
              id={`${panelId}-tab-${index}`}
              aria-selected={selected}
              aria-controls={panelId}
              tabIndex={selected ? 0 : -1}
              onClick={() => {
                onActivePathChange(path);
              }}
              onKeyDown={(event) => {
                onTabKeyDown(event, index);
              }}
              className={`min-h-9 whitespace-nowrap rounded-t-control border border-b-0 px-3 font-mono text-sm ${selected ? 'border-line-subtle bg-raised text-ink' : 'border-transparent text-ink-muted hover:text-ink'}`}
            >
              {path}
            </button>
          );
        })}
      </div>
      <div
        role="tabpanel"
        id={panelId}
        aria-labelledby={`${panelId}-tab-${Math.max(paths.indexOf(activePath), 0)}`}
        className="h-80 overflow-hidden xl:h-auto xl:flex-1"
      >
        <CodeMirror
          value={files[activePath] ?? ''}
          onChange={(value) => {
            onChange(activePath, value);
          }}
          extensions={extensions}
          theme="none"
          editable={!disabled}
          height="100%"
          style={{ height: '100%' }}
          basicSetup={false}
        />
      </div>
      <div className="shrink-0 border-t border-line-subtle bg-sunken px-3 py-1.5 text-xs text-ink-muted">
        <p className="m-0">Press Escape, then Tab, to move focus out of the editor.</p>
        <details className="group">
          <summary className="flex min-h-6 cursor-pointer list-none items-center gap-1 text-ink-secondary hover:text-ink">
            <ChevronRight
              aria-hidden="true"
              className="h-3.5 w-3.5 transition-transform duration-fast group-open:rotate-90"
            />
            {lexicon.editorShortcuts}
          </summary>
          <dl className="m-0 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 py-1.5">
            {editorShortcuts().map(([keys, action]) => (
              <div key={keys} className="contents">
                <dt className="font-mono text-ink">{keys}</dt>
                <dd className="m-0">{action}</dd>
              </div>
            ))}
          </dl>
        </details>
      </div>
    </div>
  );
}
