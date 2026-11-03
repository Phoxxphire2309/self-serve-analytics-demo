# How we work in this repo

Every change goes through the same loop. Nobody pushes to `main` directly; `main` only changes
by merging a reviewed pull request (PR) whose checks are green.

```
update main → branch → change → commit → push → pull request → checks → review → merge → tidy up
                                                     ↑                     │
                                                     └── push fixes ◄──────┘ (changes requested)
```

## 1. Start from an up-to-date main

```bash
git switch main
git pull
```

## 2. Make a branch

One branch per change, named `<type>/<what-it-does>`:

| Type | Use for | Example |
|---|---|---|
| `feat/` | a new model, metric or skill capability | `feat/nation-on-orders` |
| `fix/` | something that gives a wrong answer | `fix/revenue-date-basis` |
| `eval/` | adding or fixing eval cases | `eval/orders-q1-1997` |
| `docs/` | README, CONTRIBUTING, reference docs only | `docs/snowflake-setup` |

```bash
git switch -c eval/orders-q1-1997
```

## 3. Make the change

- **Changed anything in `models/marts/` or `models/semantic/`?** Update the matching file in
  `.claude/skills/tpch-warehouse/` in the same branch. CI fails the PR otherwise.
- **Changed a skill?** Bump `metadata.version` at the top of its `SKILL.md` (1.0.0 → 1.1.0).
  Eval results record the version, so you can see which version gave which answer.
- Run `dbt build` and make sure it ends `ERROR=0`.
- Run the evals the change could affect: `python evals/run_evals.py --only <ids>`.
- Ask Claude Code to review your branch before anyone else does: `/code-review` in a session.

## 4. Commit

Small commits, one idea each. Look at what you're about to commit before you commit it.

```bash
git status                 # what changed
git diff                   # the changes themselves
git add -p                 # stage piece by piece, so nothing sneaks in
git commit -m "Add Q1 1997 order count eval case"
```

A good message is a short summary in the imperative ("Add…", "Fix…"), under about 72 characters.
If the why isn't obvious, add a blank line and a sentence or two.

Never commit data, `analytics.duckdb`, `evals/results/` or any password or key. `.gitignore`
already excludes the files; secrets belong in environment variables or GitHub secrets.

## 5. Push

```bash
git push -u origin eval/orders-q1-1997    # first push of a new branch
git push                                  # every push after that
```

## 6. Open a pull request

```bash
gh pr create --fill          # or click "Compare & pull request" on GitHub
gh pr create --fill --draft  # not ready for review yet
```

Fill in the template: what changed, whether skill docs changed, and eval results before and after.
Keep PRs small enough to review in ten minutes.

## 7. Checks

| Check | What it does | If it's red |
|---|---|---|
| **dbt CI / build** | builds and tests every model, validates the semantic layer, re-derives the pinned eval answers | open **Details**, read the first error, fix, push again |
| **Skill drift check** | fails when a governed model or metric changed and its skill doc didn't | update the doc in `.claude/skills/`, or add the `no-skill-change` label if meaning didn't change |
| **Agent evals** | runs the eval questions through Claude (only when an API key secret is set) | look at which cases failed in the job summary |

Pushing again to the same branch updates the PR and reruns the checks. No need to open a new one.

## 8. Review

**Asking for one:** `gh pr edit --add-reviewer <github-username>`, or the Reviewers box on the PR.

**Doing one** (Files changed tab). Check, in this order:

1. Does the PR do what its description says, and nothing else?
2. If a model or metric changed, did the skill docs change to match, are they still true, and
   was the skill's `metadata.version` bumped?
3. Do the numbers still make sense? Pinned eval answers only change with a reason in the PR.
4. Would a stakeholder get a different answer to a common question after this merges? Is that intended?
5. Is anything committed that shouldn't be (data, keys, local paths)?

Comment on specific lines. Use a **suggestion** block when you can show the fix. Prefix small
points with `nit:` so the author knows they're optional. Then finish the review with one of:

- **Comment** — questions only, no verdict yet
- **Request changes** — must be fixed before merging
- **Approve** — good to merge once checks are green

**Responding to one:** reply to each comment, push the fixes, resolve the threads you've handled,
then click **Re-request review**.

## 9. Merge and tidy up

When it's approved and every required check is green: **Squash and merge** (one tidy commit on
`main` per PR), then **Delete branch**. Locally:

```bash
git switch main
git pull
git branch -d eval/orders-q1-1997
```

## When things go sideways

| Situation | Do this |
|---|---|
| Staged a file by mistake | `git restore --staged <file>` |
| Typo in the last commit, not pushed yet | `git commit --amend` |
| `main` moved on while your PR was open | **Update branch** on the PR, or `git pull --rebase origin main` then `git push --force-with-lease` |
| Merge conflict | open the file, keep the right lines, delete the `<<<<<<<` / `>>>>>>>` markers, `git add`, continue |
| Something merged that shouldn't have | `git revert <commit>` on a new branch and open a PR. Never rewrite `main`'s history. |
