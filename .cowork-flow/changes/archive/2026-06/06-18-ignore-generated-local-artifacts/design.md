## Design

This is a repository hygiene change, not a runtime contract change.

- Use the root `.gitignore` as the single enforcement point for local generated
  directories that belong to this checkout only.
- Keep the change narrow: add ignore entries only for the currently observed
  noise sources.
- Lock the behavior with a lightweight test that reads the committed
  `.gitignore` content and asserts the required entries remain present.

## Rationale

The template runtime directory already stays out of packaged output, but that
packaging safeguard does not help local `git status`. Root ignore rules are the
correct place to suppress local noise for this repository.
