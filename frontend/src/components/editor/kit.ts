import type { Completion, CompletionContext, CompletionResult } from '@codemirror/autocomplete';
import { syntaxTree } from '@codemirror/language';
import type { EditorState } from '@codemirror/state';
import { hoverTooltip } from '@codemirror/view';

import api from './forgeway-kit-api.json';

/**
 * The forgeway_kit public API, generated from the package by scripts/kit_api.py (a grader test
 * fails when it drifts), so completions and hovers always match what the sandbox imports.
 */
export interface KitMember {
  name: string;
  kind: string;
  signature: string;
  doc: string;
}

export interface KitSymbol extends KitMember {
  members: KitMember[];
}

export const KIT_MODULE = api.module;
export const KIT_SYMBOLS: readonly KitSymbol[] = api.symbols;
const byName = new Map(KIT_SYMBOLS.map((symbol) => [symbol.name, symbol]));

/** Names that refer to the module itself: `forgeway_kit` and any `import forgeway_kit as x`. */
function moduleAliases(state: EditorState): Set<string> {
  const aliases = new Set([KIT_MODULE]);
  const pattern = new RegExp(`^\\s*import\\s+${KIT_MODULE}\\s+as\\s+(\\w+)`, 'gm');
  for (const match of state.doc.toString().matchAll(pattern)) {
    if (match[1]) aliases.add(match[1]);
  }
  return aliases;
}

const completionType = (kind: string) =>
  kind === 'function' || kind === 'method' ? kind : kind === 'class' ? 'class' : 'property';

/** The signature after the name: `(text: str) -> int`, or the field's type. */
function signatureDetail(symbol: KitMember) {
  const start = symbol.signature.indexOf(symbol.name) + symbol.name.length;
  return symbol.signature.slice(start).replace(/^: /, '') || undefined;
}

/** Inline `code` spans become <code>; everything else stays text. */
function appendDoc(parent: HTMLElement, doc: string) {
  doc.split('`').forEach((part, index) => {
    if (part === '') return;
    if (index % 2 === 1) parent.appendChild(document.createElement('code')).textContent = part;
    else parent.appendChild(document.createTextNode(part));
  });
}

/** Signature and the docstring's first paragraph, for hovers and the completion info panel. */
export function renderKitDoc(symbol: KitMember): HTMLElement {
  const root = document.createElement('div');
  root.className = 'cm-kit-doc';
  const signature = root.appendChild(document.createElement('pre'));
  signature.className = 'cm-kit-signature';
  signature.textContent = symbol.signature;
  if (symbol.doc) {
    const doc = root.appendChild(document.createElement('p'));
    doc.className = 'cm-kit-summary';
    appendDoc(doc, symbol.doc);
  }
  return root;
}

const toOption = (symbol: KitMember): Completion => ({
  label: symbol.name,
  type: completionType(symbol.kind),
  detail: signatureDetail(symbol),
  info: () => renderKitDoc(symbol),
});

const topLevelOptions = KIT_SYMBOLS.map(toOption);

const inStringOrComment = (state: EditorState, pos: number) =>
  /String|Comment/.test(syntaxTree(state).resolveInner(pos, -1).name);

/** Completion for the forgeway_kit API: module members, class members, and import lists. */
export function kitCompletionSource(context: CompletionContext): CompletionResult | null {
  if (inStringOrComment(context.state, context.pos)) return null;
  const line = context.state.doc.lineAt(context.pos);
  const before = line.text.slice(0, context.pos - line.from);

  const imported = new RegExp(`^\\s*from\\s+${KIT_MODULE}\\s+import\\s+[\\w\\s,()]*?(\\w*)$`).exec(
    before,
  );
  if (imported) {
    return {
      from: context.pos - (imported[1]?.length ?? 0),
      options: topLevelOptions,
      validFor: /^\w*$/,
    };
  }

  const member = /(\w+)\.(\w*)$/.exec(before);
  if (member) {
    const [, owner = '', partial = ''] = member;
    const from = context.pos - partial.length;
    if (moduleAliases(context.state).has(owner)) {
      return { from, options: topLevelOptions, validFor: /^\w*$/ };
    }
    const symbol = byName.get(owner);
    if (symbol && symbol.members.length > 0) {
      return { from, options: symbol.members.map(toOption), validFor: /^\w*$/ };
    }
    return null;
  }

  const word = context.matchBefore(/\w+/);
  if (!word && !context.explicit) return null;
  return {
    from: word?.from ?? context.pos,
    options: [
      ...topLevelOptions,
      { label: KIT_MODULE, type: 'namespace', detail: 'module', boost: -1 },
    ],
    validFor: /^\w*$/,
  };
}

/** The kit symbol (or class member) at `pos`, with the range of the word it covers. */
export function kitSymbolAt(
  state: EditorState,
  pos: number,
): { symbol: KitMember; from: number; to: number } | null {
  const word = state.wordAt(pos);
  if (!word || inStringOrComment(state, word.to)) return null;
  const name = state.sliceDoc(word.from, word.to);
  const owner = /(\w+)\.$/.exec(state.sliceDoc(Math.max(0, word.from - 80), word.from));

  let symbol: KitMember | undefined;
  if (owner?.[1]) {
    if (moduleAliases(state).has(owner[1])) symbol = byName.get(name);
    else symbol = byName.get(owner[1])?.members.find((item) => item.name === name);
  } else {
    symbol = byName.get(name);
  }
  return symbol ? { symbol, from: word.from, to: word.to } : null;
}

/** Hovering a kit name shows its signature and summary. The tooltip never takes focus. */
export const kitHover = hoverTooltip((view, pos) => {
  const found = kitSymbolAt(view.state, pos);
  if (!found) return null;
  return {
    pos: found.from,
    end: found.to,
    above: true,
    create: () => ({ dom: renderKitDoc(found.symbol) }),
  };
});
