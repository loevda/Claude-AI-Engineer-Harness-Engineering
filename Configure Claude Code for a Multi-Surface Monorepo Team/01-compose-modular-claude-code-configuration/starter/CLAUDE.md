# E-Commerce Platform — Shared Claude Code Conventions

This file is the **project-level** entry point for the e-commerce monorepo. Every teammate's Claude session loads it automatically.

## Scope: what belongs here vs. elsewhere

<!--
TODO: Add a side-by-side table distinguishing project-level (`./CLAUDE.md`, `.claude/`),
      user-level (`~/.claude/`), and directory-level (subdir `CLAUDE.md`) scopes. The table
      MUST explicitly state that user-level settings are NOT shared with teammates via
      version control, and MUST include one concrete example of content that belongs at
      user-level (e.g. preferred commit message style).
-->

| Scope | Where it lives | Shared with the team? | Typical content |
|-------|----------------|-----------------------|-----------------|
| **Project-level** | `./CLAUDE.md`, `.claude/standards/`, `.claude/rules/` | Yes — committed to git | Repo-wide conventions: shared standards, path-scoped rules, team commands & skills. |
| **User-level** | `~/.claude/CLAUDE.md`, `~/.claude/commands/`, `~/.claude/skills/` | **No — not shared via version control** | Personal preferences: your preferred commit-message style, editor snippets, personal aliases. |
| **Directory-level** | a `CLAUDE.md` inside a subdirectory | Yes — committed to git | Narrower conventions for one subtree; we prefer `.claude/rules/` globs for cross-cutting cases. |

<!-- TODO: Add a short paragraph tying the table back to the team's intent. -->

Anything the whole team must agree on belongs in the project-level files above, where it is version-controlled and reviewable in every PR. Anything that is purely yours — your preferred commit-message style, a personal `/standup` command, a favorite prompt template — belongs under `~/.claude/`, which stays on your machine and is **not shared** with teammates through git.

## Shared standards (modular via @-imports)

The actual conventions live in focused files so this entry point stays scannable:

<!--
TODO: Use an `@`-import (a bare `@` followed immediately by the path) to pull in each standards file from .claude/standards/.

The `@`-import directive is a BARE LINE on its own — an `@` immediately followed by the path, with no `import` keyword — e.g.

    @.claude/standards/frontend.md

It is NOT Markdown link syntax like `[name](path)`. That is a common first-attempt
mistake — Markdown links render but they do not actually import the file's contents
into the session.

Four standards files already exist for you under `.claude/standards/`:
frontend.md, api.md, database.md, testing.md. Add one `@`-import line for each.
-->

@.claude/standards/frontend.md
@.claude/standards/api.md
@.claude/standards/database.md
@.claude/standards/testing.md

Path-scoped rules in [.claude/rules/](.claude/rules/) layer on top of these standards and activate only when Claude is editing matching files (React components, API handlers, test files).

## Repository layout

```
src/components/   React components (functional + hooks)
src/pages/        Top-level routes
src/api/          Node.js API handlers
src/db/           PostgreSQL repository-pattern modules
```

Tests are co-located: `Foo.tsx` lives next to `Foo.test.tsx`.

## Troubleshooting

<!--
TODO: Add a one-liner telling teammates that if a CLAUDE.md instruction isn't being
      followed, they should run the Claude Code command that lists exactly which
      configuration files actually loaded for the current session.

      (Hint: the command starts with `/m` and is named after Claude's memory.)
-->

If a `CLAUDE.md` instruction isn't being followed, run `/memory` in the Claude session — it lists exactly which configuration files actually loaded for the current session, so you can confirm whether the file (and its `@`-imports) were picked up at all.

## Team workflows

- `/review <pr-ref>` — codified PR review checklist. (You will author this in Exercise 2.)
- `/deploy-check` — read-only pre-deployment validation. (You will author this in Exercise 3.)

For decisions about when to use plan mode vs. direct execution on this codebase, you will produce a team decision doc in Exercise 4.
