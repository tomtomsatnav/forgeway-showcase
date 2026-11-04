import {
  acceptCompletion,
  autocompletion,
  closeBrackets,
  closeBracketsKeymap,
  completeFromList,
  completionKeymap,
  ifNotIn,
} from '@codemirror/autocomplete';
import {
  defaultKeymap,
  history,
  historyKeymap,
  indentWithTab,
  selectLine,
  temporarilySetTabFocusMode,
} from '@codemirror/commands';
import { python, pythonLanguage } from '@codemirror/lang-python';
import { bracketMatching, foldGutter, foldKeymap, indentOnInput } from '@codemirror/language';
import { highlightSelectionMatches, openSearchPanel, searchKeymap } from '@codemirror/search';
import { EditorState, type Extension } from '@codemirror/state';
import {
  drawSelection,
  dropCursor,
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  highlightSpecialChars,
  keymap,
  lineNumbers,
  rectangularSelection,
  type Command,
} from '@codemirror/view';
import { indentationMarkers } from '@replit/codemirror-indentation-markers';

import { pythonIndentation } from './indentation';
import { kitCompletionSource, kitHover } from './kit';

/**
 * Plain keywords. The Python language already completes builtins, local names and snippets for
 * `def`, `for`, `while`, `try`, `if`, `class`, `import` and `from`, but not the rest.
 */
const keywordCompletion = ifNotIn(
  ['String', 'FormatString', 'Comment', 'PropertyName'],
  completeFromList(
    'and as assert async await break case continue del elif else except finally global in is lambda match nonlocal not or pass raise return with yield'
      .split(' ')
      .map((label) => ({ label, type: 'keyword' })),
  ),
);

/** VS Code's Replace: the search panel with the replace field focused. */
const openReplacePanel: Command = (view) => {
  openSearchPanel(view);
  const field = view.dom.querySelector<HTMLInputElement>('.cm-search input[name=replace]');
  field?.focus();
  field?.select();
  return true;
};

/**
 * Bindings VS Code users expect that CodeMirror's defaults lack or bind differently. Most of
 * the rest (Mod-/, Alt-Up/Down, Shift-Alt-Up/Down, Mod-f, Mod-d, folding) are CodeMirror's own.
 */
const vsCodeKeymap = [
  { key: 'Tab', run: acceptCompletion },
  { key: 'Mod-l', run: selectLine, preventDefault: true },
  { key: 'Mod-h', run: openReplacePanel, preventDefault: true },
  { key: 'Mod-Alt-f', run: openReplacePanel, preventDefault: true },
];

/**
 * CodeMirror lets Tab leave the editor for two seconds after Escape, but only when no binding
 * used the Escape, so closing the completion list or the search panel would swallow the way
 * out. Observing every Escape keeps it: Escape, then Tab, always moves focus on.
 */
const escapeThenTabLeaves = EditorView.domEventObservers({
  keydown: (event, view) => {
    if (event.key === 'Escape') temporarilySetTabFocusMode(view);
  },
});

/**
 * Everything the exercise editor needs to edit Python as VS Code does. Tab indents, so
 * Escape then Tab leaves the editor (CodeMirror's tab-focus mode; DESIGN.md, Accessibility).
 */
export function pythonEditorSetup(): Extension {
  return [
    python(),
    pythonIndentation(),
    escapeThenTabLeaves,
    pythonLanguage.data.of({ autocomplete: keywordCompletion }),
    pythonLanguage.data.of({ autocomplete: kitCompletionSource }),
    lineNumbers(),
    highlightActiveLineGutter(),
    highlightSpecialChars(),
    history(),
    foldGutter(),
    drawSelection(),
    dropCursor(),
    EditorState.allowMultipleSelections.of(true),
    // Alt-click adds a cursor, as in VS Code; Shift-Alt-drag selects a column.
    EditorView.clickAddsSelectionRange.of((event) => event.altKey),
    rectangularSelection({ eventFilter: (event) => event.altKey && event.shiftKey }),
    indentOnInput(),
    bracketMatching(),
    closeBrackets(),
    autocompletion({ icons: true }),
    kitHover,
    highlightActiveLine(),
    highlightSelectionMatches(),
    indentationMarkers({
      colors: {
        light: 'var(--border-subtle)',
        dark: 'var(--border-subtle)',
        activeLight: 'var(--border-strong)',
        activeDark: 'var(--border-strong)',
      },
    }),
    keymap.of([
      ...vsCodeKeymap,
      ...closeBracketsKeymap,
      ...defaultKeymap,
      ...searchKeymap,
      ...historyKeymap,
      ...foldKeymap,
      ...completionKeymap,
      indentWithTab,
    ]),
  ];
}

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.userAgent);

/** The keyboard shortcuts, worded for this platform, for the editor's Shortcuts list. */
export function editorShortcuts(mac = isMac): readonly (readonly [keys: string, action: string])[] {
  const mod = mac ? 'Cmd' : 'Ctrl';
  const alt = mac ? 'Option' : 'Alt';
  return [
    ['Tab / Shift+Tab', 'Indent or dedent the line or selection'],
    ['Escape, then Tab', 'Move focus out of the editor'],
    [`Ctrl+Space`, 'Show completions (Enter or Tab accepts)'],
    [`${mod}+/`, 'Comment or uncomment the line'],
    [`${mod}+F`, 'Find'],
    [mac ? 'Cmd+Option+F' : 'Ctrl+H', 'Replace'],
    [`${mod}+D`, 'Select the next occurrence'],
    [`${alt}+click`, 'Add a cursor'],
    [`${alt}+Up / ${alt}+Down`, 'Move the line up or down'],
    [`Shift+${alt}+Down`, 'Duplicate the line'],
    [`${mod}+L`, 'Select the line'],
    [mac ? 'Cmd+Option+[ / ]' : 'Ctrl+Shift+[ / ]', 'Fold or unfold the block'],
    [`${mod}+Z / ${mod}+Shift+Z`, 'Undo or redo'],
  ];
}
