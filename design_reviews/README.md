# Design reviews

Independent reviews of the board before it is ordered, by other LLMs and by the
author, each in its own dated directory so that several can run at once without
touching each other or the project:

    design_reviews/
      DESIGN_REVIEW_PROMPT.md           the brief to give a reviewer
      <YYYY-MM-DD>_<Model-Version>/     one reviewer's directory: REPORT.md and
                                        everything it made or copied
      <YYYY-MM-DD>_<Model-Version>/project/   a reviewer's working copy of the
                                        project (gitignored; never committed)

A reviewer only ever writes inside its own directory.  The brief says what to review,
how to work and what the report must contain.  A later round gets a later date, so the
rounds sort themselves.

| round | directory | reviewer | verdict |
|---|---|---|---|
| 1 | `2026-11-03_Claude-Fable-5.1/` | the author (Claude Fable 5.1), before any other report | order after named fixes: 11 findings, one circuit fault (the POLARIZE IN clamp against the TS391's -0.3 V input limit), the rest labels and documents; all applied in the next commit |

Rev A, 2026-11-03, is ready for outside reviewers: the brief is `DESIGN_REVIEW_PROMPT.md`.
