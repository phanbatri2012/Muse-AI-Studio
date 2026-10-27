# CLAUDE.md

Keep this file aligned in intent with `AGENTS.md`. `AGENTS.md` remains part of the current repo workflow; this file is the minimal Claude-facing mirror.

## 1. Think Before Coding

- State assumptions explicitly.
- If multiple interpretations exist, surface them instead of choosing silently.
- Prefer the simpler approach when it solves the request.
- Stop and ask when something important is genuinely unclear.

## 2. Simplicity First

- Write the minimum code that solves the requested problem.
- Do not add speculative abstractions, configuration, or edge-case handling that was not requested.
- If a solution feels overbuilt, simplify it before shipping.

## 3. Surgical Changes

- Touch only the code needed for the task.
- Do not refactor or clean up unrelated areas.
- Match the existing style of the code you are editing.
- Remove only the unused code that your own change creates.

## 4. Goal-Driven Verification

- Define a concrete verification path before changing code.
- Prefer reproducing a bug with a targeted test before fixing it.
- Do not claim success without either running the relevant checks or clearly naming the blocker.

## 5. Finish The Agreed Plan First

- If there is already an agreed plan, complete that scope before proposing extra improvements.
- Do not mix optional upgrades into unfinished planned work.

## Repo-Specific Checks

- Primary verification command: `./scripts/run_gui_tests.sh`
- Recovery-focused suite: `./scripts/run_gui_tests.sh tests.test_idea_recovery`
- GUI tests depend on `PyQt6` and `imageio_ffmpeg`.
- If the local PyQt or `imageio_ffmpeg` environment is missing, report that as a blocker instead of assuming the GUI suite passed.
- Keep fixes tightly scoped to the requested change, especially around Idea recovery and GUI behavior.

## Merging Branches (CRITICAL)

**NEVER run `git merge <branch>` directly.** Always use the safe merge script:

```bash
./scripts/merge-branch.sh <branch-name>
```

**Why:** Worktrees and feature branches are often created from an older commit. If you merge directly, the merge uses the old base version of files, silently overwriting newer commits on main. This happened with the license branch merge (d942d85) which overwrote 20+ commits worth of workflow improvements.

The script automatically:
1. Detects if the branch is behind main
2. Rebases the branch onto current main first
3. Then merges safely with `--no-ff`

A `pre-merge-commit` git hook also blocks direct merges from stale branches as a safety net.
