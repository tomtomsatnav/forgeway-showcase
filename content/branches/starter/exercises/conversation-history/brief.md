# Keeping conversation history

Model APIs are stateless. The model does not remember your last call; if the user says
"make it shorter", it only knows what "it" is because you sent the previous question and
answer again. A chat application is therefore mostly bookkeeping: keep the list of turns and
send all of it each time.

```
turn 1 sends: user "Name a fruit"
turn 2 sends: user "Name a fruit", assistant "Apple", user "Another one"
```

Roles must alternate, and the final message must be from the user. If you forget to store the
assistant's reply, the next request has two user messages in a row and the model loses its
own side of the conversation.

## Your task

Implement the `Chat` class in `chat.py`.

- `Chat(client, system=None)` starts an empty conversation.
- `send(text)` adds the user turn, calls the model with the full history (and the system
  prompt, if any), adds the assistant's reply to the history, and returns the reply text.
- `history` returns the conversation so far as a list of `Message` objects. Changing the
  returned list must not change the chat's own history.
- Each `Chat` has its own history.
- If the model call raises, let the error propagate and leave the history exactly as it was,
  so the user turn is not left dangling and the caller can simply retry.
