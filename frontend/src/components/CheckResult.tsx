import { CircleCheck, CircleX } from 'lucide-react';

import type { CheckResult as CheckResultData } from '../api/types';

export interface MessagePart {
  kind: 'prose' | 'code';
  text: string;
}

/** A line that introduces a value on the lines below it, such as "… Expected:" or "Got:". */
const INTRODUCER = /\b(expected|got|received|actual|returned|sent|wanted|imported)\s*:\s*$/i;
/** A line that is itself a value, such as "Got: 'hello'". */
const VALUE_LINE = /^(expected|got|received|actual|returned|wanted)\s*:\s*\S/i;
const FENCE = /^\s*```/;
const INDENTED = /^(\t| {2,})\S/;

/**
 * Splits a check's message into prose and code-like runs: fenced or indented blocks, "Expected:"
 * and "Got:" values, and whatever follows a line that introduces one. The rest is prose.
 */
export function splitMessage(message: string): MessagePart[] {
  const parts: MessagePart[] = [];
  const push = (kind: MessagePart['kind'], line: string) => {
    const last = parts.at(-1);
    if (last?.kind === kind) last.text += `\n${line}`;
    else parts.push({ kind, text: line });
  };
  let fenced = false;
  let introduced = false;
  for (const line of message.split('\n')) {
    if (FENCE.test(line)) {
      fenced = !fenced;
      continue;
    }
    if (fenced) {
      push('code', line);
    } else if (INTRODUCER.test(line)) {
      push('prose', line);
      introduced = true;
    } else if (introduced || VALUE_LINE.test(line) || INDENTED.test(line)) {
      push('code', line);
    } else {
      push('prose', line);
    }
  }
  return parts
    .map((part) => ({ ...part, text: part.text.replace(/^\n+|\n+$/g, '') }))
    .filter((part) => part.text.trim() !== '');
}

/** One check: title, a pass/fail mark (icon and word), the message in a well, and the learner's output. */
export function CheckResult({ check }: { check: CheckResultData }) {
  const Icon = check.passed ? CircleCheck : CircleX;
  return (
    <div className="space-y-2">
      <div className="flex items-start justify-between gap-3">
        <h3 className="m-0 font-ui text-base font-semibold">{check.title}</h3>
        <span
          className={`inline-flex shrink-0 items-center gap-1.5 ${check.passed ? 'text-success' : 'text-danger'}`}
        >
          <Icon aria-hidden="true" className="h-4 w-4" />
          <span className="label-caps">{check.passed ? 'Passed' : 'Failed'}</span>
        </span>
      </div>
      {check.message !== '' && (
        <div className="space-y-2 rounded-control bg-sunken px-3 py-2 text-sm text-ink">
          {splitMessage(check.message).map((part, index) =>
            part.kind === 'code' ? (
              <pre key={index} className="m-0 whitespace-pre-wrap break-words font-mono text-sm">
                {part.text}
              </pre>
            ) : (
              <p key={index} className="m-0 whitespace-pre-wrap font-ui">
                {part.text}
              </p>
            ),
          )}
        </div>
      )}
      {check.output !== '' && (
        <details className="group">
          <summary className="min-h-6 cursor-pointer text-sm text-ink-secondary hover:text-ink">
            Your output
          </summary>
          <pre
            tabIndex={0}
            className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-control bg-sunken px-3 py-2 font-mono text-sm text-ink"
          >
            {check.output}
          </pre>
        </details>
      )}
    </div>
  );
}
