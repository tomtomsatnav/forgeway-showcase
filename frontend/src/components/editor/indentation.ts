import { getIndentation, indentService, indentUnit } from '@codemirror/language';
import { EditorState, type Extension } from '@codemirror/state';
import { EditorView } from '@codemirror/view';

/** Four spaces, as PEP 8 and VS Code's Python defaults have it. */
export const INDENT_WIDTH = 4;

/**
 * A line that ends its block: the next line steps back one level, as VS Code does after
 * `return`, `pass`, `break`, `continue` and `raise`. A line left open by a bracket, a comma or a
 * backslash continues the statement, so it does not count.
 */
const BLOCK_END = /^\s*(return|pass|break|continue|raise)\b/;
const CONTINUES = /[([{,\\]\s*(#.*)?$/;

/**
 * Indentation for a new line after a block-ending statement. Everything else, including the
 * indent after a line ending in `:` and the dedent for `else:`/`elif`/`except`/`finally:`, comes
 * from the Python language's own indentation rules.
 */
const dedentAfterBlockEnd = indentService.of((context, pos) => {
  // With a simulated break at `pos` (Enter), the line before is the text before the break;
  // when re-indenting an existing line, it is the document line above.
  const here = context.lineAt(pos, -1);
  let previous = here.text;
  if (here.from === pos) {
    if (pos === 0) return undefined;
    previous = context.state.doc.lineAt(pos - 1).text;
  }
  if (!BLOCK_END.test(previous) || CONTINUES.test(previous)) return undefined;
  const indent = context.countColumn(previous, previous.search(/\S|$/));
  return Math.max(0, indent - context.unit);
});

const leadingColumns = (line: string) => {
  const whitespace = /^[ \t]*/.exec(line)?.[0] ?? '';
  return whitespace.replace(/\t/g, ' '.repeat(INDENT_WIDTH)).length;
};

const dropColumns = (line: string, columns: number) => {
  let column = 0;
  let index = 0;
  while (index < line.length && column < columns) {
    const char = line[index];
    if (char === ' ') column += 1;
    else if (char === '\t') column += INDENT_WIDTH;
    else break;
    index += 1;
  }
  return line.slice(index);
};

/**
 * Re-indent multi-line pasted code to where it lands, keeping its lines' relative indentation.
 * Copying from the middle of a line usually loses the first line's indentation, so when the first
 * line starts flush and the rest are indented, the rest set the reference level (one level less
 * when the first line opens a block).
 */
export function reindentPaste(text: string, state: EditorState): string {
  if (!text.includes('\n') || state.selection.ranges.length > 1) return text;
  const lines = text.replace(/\r\n?/g, '\n').split('\n');
  const [first = '', ...rest] = lines;
  const restIndents = rest.filter((line) => line.trim() !== '').map(leadingColumns);
  if (restIndents.length === 0) return text;

  const cursor = state.selection.main.from;
  const line = state.doc.lineAt(cursor);
  const before = line.text.slice(0, cursor - line.from);
  const atLineStart = before.trim() === '';

  let reference = Math.min(...restIndents);
  if (atLineStart && first.trim() !== '' && /^[ \t]/.test(first)) {
    reference = Math.min(reference, leadingColumns(first));
  } else if (/:\s*(#.*)?$/.test(first) && reference >= INDENT_WIDTH) {
    reference -= INDENT_WIDTH;
  }

  let target: number;
  let head = first;
  if (atLineStart) {
    // On a blank line with no indentation typed yet, use the indentation the code needs there.
    target =
      before === '' && line.text.trim() === ''
        ? (getIndentation(state, line.from) ?? 0)
        : leadingColumns(before);
    const firstRelative = Math.max(0, leadingColumns(first) - reference);
    head = ' '.repeat(target - leadingColumns(before) + firstRelative) + first.trimStart();
  } else {
    target = leadingColumns(line.text);
  }

  const body = rest.map((current) => {
    if (current.trim() === '') return '';
    const relative = leadingColumns(current) - reference;
    return (
      ' '.repeat(Math.max(0, target + relative)) + dropColumns(current, leadingColumns(current))
    );
  });
  return [head, ...body].join(state.lineBreak);
}

/** Python indentation: four-space unit, VS Code-style dedent, paste re-indentation. */
export function pythonIndentation(): Extension {
  return [
    indentUnit.of(' '.repeat(INDENT_WIDTH)),
    EditorState.tabSize.of(INDENT_WIDTH),
    dedentAfterBlockEnd,
    EditorView.clipboardInputFilter.of(reindentPaste),
  ];
}
