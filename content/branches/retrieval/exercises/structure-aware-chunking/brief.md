# Structure-aware chunking

Fixed-size chunks cut wherever the character count lands: mid-sentence, mid-table, or across two
unrelated topics. Most real documents already have structure (headings, paragraphs), and
respecting it gives chunks that mean something on their own.

A structure-aware chunker also keeps the **heading as metadata**. A chunk reading "Payment is due
within 30 days" is ambiguous; the same chunk labelled `Invoices` is not. In production that label
feeds filters, citations and the prompt.

```markdown
# Billing
Invoices are sent monthly.

Payment is due in 30 days.

## Refunds
Refunds take 5 days.
```

With `max_chars=100` this gives two chunks: `("Invoices are sent monthly.\n\nPayment is due in 30 days.", "Billing")`
and `("Refunds take 5 days.", "Refunds")`. Small paragraphs are merged; sections never are.

## Your task

Implement `chunk_markdown(text, max_chars=300)` in `chunker.py`, returning `Chunk(text, heading)` objects:

- a heading is a line starting with 1 to 6 `#` characters followed by a space; the heading line itself is not part of any chunk's text, and `heading` is its text without the `#`s (`""` before the first heading);
- paragraphs are separated by blank lines;
- within a section, pack consecutive paragraphs into a chunk, joined by `"\n\n"`, while the chunk stays at most `max_chars`;
- a paragraph longer than `max_chars` is split into pieces of whole words, each at most `max_chars`, joined by single spaces; those pieces then take part in packing as normal;
- a section with no body gives no chunk; chunks never span two sections.
