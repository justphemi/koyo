# Contributing to Koyo

Thanks for wanting to help. Koyo is a small project and every contribution
counts, whether that is a bug report, a feature idea, or a pull request.

## Ways to contribute

### Report a bug

Open an issue with enough detail to reproduce it:

- The version of koyoapp you are on (`koyoapp --version`)
- What you ran and what you expected to happen
- What actually happened instead
- If the issue is in the dev server or build, the tail of `.koyo/dev-server.log`

### Suggest a feature

Open an issue describing what you want to build and why it matters. A small
example of the code you imagine using it with helps a lot.

### Ask questions

Open a discussion and tag it as a question. No question is too basic.

### Write code

Look for issues labeled `good first issue` if you want a gentle start. For
anything bigger, comment on the issue first so nobody works on the same
thing twice.

## Setting up for development

Clone the repository and install it with the test extras:

```
git clone https://github.com/justphemi/koyo.git
cd koyo
pip install -e ".[test]"
```

Run the test suite before and after your change:

```
pytest
```

All tests must pass. The CI runs the same suite on Python 3.11, 3.12, and
3.13, and it also checks that the package builds a clean wheel.

## Making a pull request

1. Fork the repository and create a branch with a descriptive name, for
   example `fix-dev-reload-loop` or `add-custom-404-page`.
2. Make your change and add or update tests to cover it.
3. Run `pytest` and make sure everything is green.
4. Push your branch and open a pull request against `main`.
5. Write a short description of what the change does and why.

PRs are small, focused, and tied to one problem. If your change is large,
split it into a few smaller PRs so it is easier to review.

## Style and rules

- Keep line lengths around 80 characters.
- No emojis in code, comments, or docs.
- No em dashes in any docs or copy. Plain hyphens only.
- Follow the conventions in the surrounding code.
- Add tests for new behavior. A change that fixes a bug should include a
  test that would have failed before the fix.

## Testing notes

- The test suite lives in `tests/`. Most tests use httpx against a built
  Starlette app, and some go through the CLI.
- `scripts/e2e.sh` runs a full end to end check: scaffold a project, build
  it, boot the dev server, exercise session state over real HTTP, then tear
  everything down. You can run it locally with `bash scripts/e2e.sh`.

## Releasing

Releases are automated. To ship a new version:

1. Bump the version in `koyoapp/__init__.py` and `pyproject.toml`.
2. Push to `main`.
3. Create a tag, for example `git tag v0.5.0 && git push origin v0.5.0`.

The CI runs the tests, builds the wheel, creates the GitHub release, and
publishes the package to PyPI automatically. You do not have to do anything
else.

## Code of conduct

Be respectful and assume good intent. This project is open to everyone.

## License

By contributing you agree that your contributions are released under the
MIT license, the same license the project uses.