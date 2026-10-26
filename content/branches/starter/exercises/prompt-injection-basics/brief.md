# Prompt injection basics

When your prompt includes text you did not write (a web page, an email, a support ticket)
that text can contain instructions, and the model may obey them. This is **prompt
injection**, and there is no perfect fix. What you can do is make the boundary between your
instructions and untrusted data as clear as possible:

1. Keep your instructions in the **system prompt**, which untrusted text never touches.
2. Wrap untrusted text in **clear delimiters** and tell the model that anything inside them is
   data, not commands.
3. **Neutralise delimiter look-alikes** inside the text. If the attacker can write
   `</document>`, they can "close" your wrapper and put their own instructions outside it.

```
<document>
Ignore all previous instructions.   <- inside the wrapper, treated as data
</document>
```

Two refinements are worth knowing. **Random-boundary delimiters** (sometimes called
"spotlighting") use a fresh unguessable marker per request, such as `<document-7f3a9c>`, so an
attacker cannot write the closing tag in advance. And the strongest defence is **least
privilege**: this lowers the risk, it does not remove it. Never give a model that reads untrusted
text the power to do something you could not tolerate an attacker doing.

## Your task

Implement `answer_about(client, document, question)` in `guarded.py`. Ask the model
`question` about the untrusted `document` and return the reply text.

- The system prompt must hold your instructions and mention the `<document>` tags. It must
  not contain the document, and must be the same whatever the document says.
- The user message must contain the document inside one `<document>` ... `</document>` pair,
  followed by the question outside the tags.
- Any `<document>` or `</document>` look-alike inside the document (any case, with or without
  spaces, with or without attributes such as `id="x"`) must be neutralised so the message contains exactly one real pair. Ordinary text in
  the document must still reach the model.
