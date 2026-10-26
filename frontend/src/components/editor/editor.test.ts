import {
  CompletionContext,
  insertBracket,
  type CompletionResult,
  type CompletionSource,
} from '@codemirror/autocomplete';
import { indentLess, indentMore, insertNewlineAndIndent } from '@codemirror/commands';
import { EditorSelection, EditorState, type Transaction } from '@codemirror/state';
import { describe, expect, it } from 'vitest';

import { reindentPaste } from './indentation';
import { KIT_SYMBOLS, kitCompletionSource, kitSymbolAt, renderKitDoc } from './kit';
import { editorShortcuts, pythonEditorSetup } from './setup';

const setup = pythonEditorSetup();

/** A state with the cursor at `|` (removed), or the selection between two `|`s. */
function stateOf(text: string) {
  const [start = 0, end = start] = [...text.matchAll(/\|/g)].map((m, i) => m.index - i);
  return EditorState.create({
    doc: text.replace(/\|/g, ''),
    selection: EditorSelection.single(start, end),
    extensions: setup,
  });
}

function run(state: EditorState, command: typeof insertNewlineAndIndent) {
  let next = state;
  command({
    state,
    dispatch: (tr: Transaction) => {
      next = tr.state;
    },
  });
  return next;
}

/** Type `text` as the browser would, so input-triggered extensions (indentOnInput) apply. */
function type(state: EditorState, text: string) {
  const { from, to } = state.selection.main;
  return state.update({
    changes: { from, to, insert: text },
    selection: { anchor: from + text.length },
    userEvent: 'input.type',
  }).state;
}

const doc = (state: EditorState) => state.doc.toString();
const cursorLine = (state: EditorState) => state.doc.lineAt(state.selection.main.head).text;

describe('Python indentation', () => {
  it('indents four spaces after a line ending in a colon', () => {
    const state = run(stateOf('def add(a, b):|'), insertNewlineAndIndent);
    expect(doc(state)).toBe('def add(a, b):\n    ');
    expect(state.selection.main.head).toBe(doc(state).length);
  });

  it('keeps the indentation of the line before', () => {
    const state = run(stateOf('def f():\n    x = 1|'), insertNewlineAndIndent);
    expect(cursorLine(state)).toBe('    ');
  });

  it.each(['return a + b', 'pass', 'break', 'continue', 'raise ValueError("no")'])(
    'dedents after %s',
    (statement) => {
      const state = run(
        stateOf(`def f():\n    for x in y:\n        ${statement}|`),
        insertNewlineAndIndent,
      );
      expect(cursorLine(state)).toBe('    ');
    },
  );

  it('does not dedent after a return left open by a bracket', () => {
    const state = run(stateOf('def f():\n    return (|'), insertNewlineAndIndent);
    expect(cursorLine(state).length).toBeGreaterThan(4);
  });

  it('dedents else: as it is typed', () => {
    let state = stateOf('if x:\n    y = 1\n    |');
    state = type(state, 'else:');
    expect(doc(state)).toBe('if x:\n    y = 1\nelse:');
  });

  it('Tab and Shift-Tab indent and dedent the selected lines by four spaces', () => {
    let state = stateOf('|a = 1\nb = 2|');
    state = run(state, indentMore);
    expect(doc(state)).toBe('    a = 1\n    b = 2');
    state = run(state, indentLess);
    expect(doc(state)).toBe('a = 1\nb = 2');
  });

  it('re-indents pasted code to where it lands, keeping its shape', () => {
    const state = stateOf('def f():\n    |');
    expect(reindentPaste('if x:\n    return 1\nreturn 2', state)).toBe(
      'if x:\n        return 1\n    return 2',
    );
  });

  it('re-indents code copied from the middle of an indented line', () => {
    const state = stateOf('class A:\n    |');
    // Copied from "        def m(self):" starting at "def": the first line lost its indent.
    expect(reindentPaste('def m(self):\n            return 1', state)).toBe(
      'def m(self):\n        return 1',
    );
  });

  it('leaves single-line pastes alone', () => {
    expect(reindentPaste('   x = 1', stateOf('|'))).toBe('   x = 1');
  });
});

describe('brackets and quotes', () => {
  const insert = (state: EditorState, bracket: string) => {
    const tr = insertBracket(state, bracket);
    expect(tr, `insertBracket(${bracket})`).not.toBeNull();
    return tr ? tr.state : state;
  };

  it('closes brackets and quotes', () => {
    expect(doc(insert(stateOf('print|'), '('))).toBe('print()');
    expect(doc(insert(stateOf('x = |'), '['))).toBe('x = []');
    expect(doc(insert(stateOf('x = |'), '"'))).toBe('x = ""');
  });

  it('closes triple-quoted strings', () => {
    expect(doc(insert(stateOf('x = ""|'), '"'))).toBe('x = """"""');
  });
});

async function complete(text: string, sources: readonly CompletionSource[], explicit = false) {
  const state = stateOf(text);
  const context = new CompletionContext(state, state.selection.main.head, explicit);
  const results = await Promise.all(sources.map(async (source) => source(context)));
  return results.filter((result): result is CompletionResult => result != null);
}

const labels = (results: CompletionResult[]) =>
  results.flatMap((result) => result.options.map((option) => option.label));

describe('completion', () => {
  it('offers kit symbols with their signatures', async () => {
    const [result] = await complete('count_t|', [kitCompletionSource]);
    const option = result?.options.find((o) => o.label === 'count_tokens');
    expect(option?.detail).toBe('(text: str) -> int');
    expect(labels(result ? [result] : [])).toEqual(
      expect.arrayContaining(['FakeModel', 'Message']),
    );
  });

  it('completes the names in a from forgeway_kit import list', async () => {
    const [result] = await complete('from forgeway_kit import Message, Fa|', [kitCompletionSource]);
    expect(result?.from).toBe('from forgeway_kit import Message, '.length);
    expect(labels(result ? [result] : [])).toContain('FakeModel');
  });

  it('completes module and class members after a dot', async () => {
    const [onModule] = await complete('import forgeway_kit as fk\nfk.use|', [kitCompletionSource]);
    expect(labels(onModule ? [onModule] : [])).toContain('use_client');
    const [onClass] = await complete('FakeModel.|', [kitCompletionSource]);
    expect(labels(onClass ? [onClass] : [])).toEqual(
      expect.arrayContaining(['complete', 'requests']),
    );
  });

  it('stays quiet inside strings and comments', async () => {
    expect(await complete('x = "Fake|"', [kitCompletionSource])).toEqual([]);
    expect(await complete('# Fake|', [kitCompletionSource])).toEqual([]);
  });

  it('combines keywords, builtins, local names and the kit', async () => {
    const text = 'total_cost = 0\ndef f():\n    |';
    const state = stateOf(text);
    const sources = state.languageDataAt<CompletionSource>(
      'autocomplete',
      state.selection.main.head,
    );
    const found = labels(await complete(text, sources, true));
    expect(found).toEqual(
      expect.arrayContaining(['return', 'print', 'len', 'total_cost', 'FakeModel']),
    );
  });
});

describe('hover', () => {
  it('shows the signature and summary of a kit symbol', () => {
    const state = stateOf('n = count_tokens("hi")');
    const found = kitSymbolAt(state, 'n = count_'.length);
    expect(found?.from).toBe(4);
    const dom = found ? renderKitDoc(found.symbol) : null;
    expect(dom?.querySelector('.cm-kit-signature')?.textContent).toBe(
      'def count_tokens(text: str) -> int',
    );
    expect(dom?.querySelector('.cm-kit-summary')?.textContent).toBe('Number of tokens in text.');
    expect(dom?.querySelector('.cm-kit-summary code')?.textContent).toBe('text');
  });

  it('shows class members and module attributes', () => {
    const member = kitSymbolAt(stateOf('FakeModel.complete'), 'FakeModel.comp'.length);
    expect(member?.symbol.signature).toMatch(/^complete\(messages: Sequence\[Message\]/);
    const attribute = kitSymbolAt(stateOf('forgeway_kit.Message'), 'forgeway_kit.Me'.length);
    expect(attribute?.symbol.name).toBe('Message');
  });

  it('ignores other names and strings', () => {
    expect(kitSymbolAt(stateOf('total = 1'), 2)).toBeNull();
    expect(kitSymbolAt(stateOf('x = "Message"'), 7)).toBeNull();
  });

  it('describes every generated symbol', () => {
    for (const symbol of KIT_SYMBOLS) expect(symbol.signature, symbol.name).toContain(symbol.name);
  });
});

describe('shortcut list', () => {
  it('words the keys for the platform', () => {
    const mac = new Map(editorShortcuts(true).map(([keys, action]) => [action, keys]));
    const other = new Map(editorShortcuts(false).map(([keys, action]) => [action, keys]));
    expect(mac.get('Comment or uncomment the line')).toBe('Cmd+/');
    expect(other.get('Comment or uncomment the line')).toBe('Ctrl+/');
    expect(other.get('Move focus out of the editor')).toBe('Escape, then Tab');
  });
});
