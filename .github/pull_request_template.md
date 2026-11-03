## What changed and why

## How I tested it
- [ ] `dbt build` ends with `ERROR=0`
- [ ] Ran `/code-review` in Claude Code on this branch and dealt with the findings

## Skill docs
- [ ] I changed a governed model or metric and updated the matching file in `.claude/skills/`
- [ ] No governed model changed, or the change doesn't affect meaning (`no-skill-change` label)

## Eval impact
<!-- For skill, model or eval changes: before/after for the affected cases, e.g.
     python evals/run_evals.py --only rev_1997 rev_europe_1996 -->

| Cases | Before | After |
|---|---|---|
|  |  |  |

---
### For the reviewer
- [ ] It does what the description says, and nothing else
- [ ] Model/metric changes come with matching skill-doc changes, and the docs are still true
- [ ] Any changed skill has its `metadata.version` bumped
- [ ] Pinned eval answers only changed with a reason given above
- [ ] Nothing committed that shouldn't be (data, keys, local paths)
