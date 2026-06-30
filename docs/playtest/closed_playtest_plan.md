# gitai Closed Playtest Plan

## Purpose

Validate that gitai is understandable, replayable, and share-worthy with outside players before a public push.

## Target Cohort

- 20-50 outside testers.
- Mix casual puzzle players, drawing-game fans, AI-curious users, and developer friends.
- At least 8 testers should play on mobile-width screens.

## Test Window

- Run for 48-72 hours.
- Freeze the deployed build during the test unless there is a launch-blocking bug.
- Use the same public URL, production-like environment variables, and operator token flow intended for launch.

## Tester Tasks

1. Open the app from the invite link.
2. Complete one DailyPuzzle submission without instructions beyond the app itself.
3. Try one replay or ghost challenge.
4. Generate or open a share card.
5. Submit one in-app playtest reaction: fun, hard, or bug.
6. Optional: use a friend code with another tester.

## Metrics To Capture

- First submission completion rate.
- Median time from open to first submission.
- Second attempt rate.
- Share-card generation or open rate.
- Friend-circle use count.
- Playtest feedback split: fun / hard / bug.
- Content report count.
- Top three recurring bug notes.
- Screenshots or share cards worth launch use.

## Success Gates

- At least 20 outside testers submit a drawing.
- At least 70% of testers complete a first submission.
- At least 35% make a second attempt or use a ghost/friend feature.
- At least 25% generate or open a share card.
- Bug feedback is below 20% of playtest reactions.
- No unresolved blocker in scoring, submission, share cards, or policy pages.

## Operator Review

Before reading qualitative comments, export the operator endpoints:

```bash
curl -H "X-Gitai-Operator-Token: $GITAI_OPERATOR_TOKEN" \
  "$GITAI_PUBLIC_WEB_URL/v1/operator/playtest-feedback"

curl -H "X-Gitai-Operator-Token: $GITAI_OPERATOR_TOKEN" \
  "$GITAI_PUBLIC_WEB_URL/v1/operator/content-reports"
```

After the test, generate the season operations report against the production runtime DB snapshot:

```bash
PYTHONPATH=src .venv310/bin/python tools/report_phase5_season_ops.py \
  --runtime-db data/runtime/playtest.sqlite \
  --season-id season-1 \
  --season-label "Season 1" \
  --season-model-version heuristic-color-shape-v1
```

## Go / No-Go

Go if the success gates pass and the only remaining tasks are production URL configuration, campaign scheduling, and real-model pair expansion.

No-go if players cannot understand the first action, submissions fail on common devices, share cards are not generated reliably, or bug feedback dominates fun feedback.
