# gitai Phase 0

gitai is now a playable web app with a deterministic scoring API, daily puzzles,
leaderboards, replayable ghosts, share cards, launch metadata, and marketing
assets checked into the repo.

Current public-launch entry points:

- Web app: `web/`
- API package: `src/gitai_phase0/`
- Deployment notes: `docs/deployment.md`
- Marketing plan: `docs/marketing/marketing_plan.md`
- Launch copy kit: `docs/marketing/launch_copy_kit.md`
- Press one-pager: `docs/marketing/press_one_pager.md`
- Closed playtest kit: `docs/playtest/`
- Public launch smoke report: `reports/public_launch/public_launch.md`

Run the main local quality gate:

```bash
npm run check
PYTHONPATH=src .venv310/bin/python tools/smoke_phase3_static.py
PYTHONPATH=src .venv310/bin/python tools/smoke_release_readiness.py --today 2026-07-06
PYTHONPATH=src .venv310/bin/python tools/smoke_public_launch.py
PYTHONPATH=src .venv310/bin/python tools/validate_production_env.py --env-file .env.production.example --allow-placeholders
PYTHONPATH=src .venv310/bin/python tools/audit_real_model_pair_coverage.py
PYTHONPATH=src .venv310/bin/python tools/audit_launch_package.py
PYTHONPATH=src .venv310/bin/python -m pytest -q
```

Manual launch blockers remain outside the repository: set production origins,
run an external closed playtest, and replace the heuristic playtest content with
broader real-model measured pairs before a serious campaign.

This workspace starts with the kill-switch validation from `PLAN.md` and
`KICKOFF.md`: prove that `X -> Y` drawings create a score spread before
building UI, database, or leaderboards.

The current scaffold includes:

- a deterministic scoring harness with temperature sweep support
- OCR-guard plumbing for typographic attacks
- pluggable judge adapters (`heuristic`, `open_clip`, `siglip`)
- synthetic sample images and metadata
- markdown, JSON, CSV, and PNG report output

The default `heuristic` judge is only a local plumbing check. The real
go/no-go decision must be run with `open_clip` and/or `siglip` once those
model dependencies and weights are available.

## Phase 0 gate result

The real-model fixture run passed the initial kill-switch gate:

- OpenCLIP `ViT-L-14/openai`: go on the synthetic `apple -> baseball` set.
- SigLIP `google/siglip-base-patch16-224`: go on the same set, with a smaller
  but still ordered spread.
- Typographic attack fixture (`BASEBALL` text) hard-zeroed in both model runs.

This is not yet proof of production-grade puzzle quality. It is enough to move
from Phase 0 into Phase 1 and build the deterministic scoring service.

## Quick run

```bash
PYTHONPATH=src python3 tools/make_phase0_samples.py
PYTHONPATH=src python3 -m gitai_phase0 run \
  --cases data/phase0/cases.json \
  --images-root data/phase0/images \
  --out-dir reports/phase0 \
  --model heuristic
PYTHONPATH=src pytest
```

## Phase 1 scoring API

Build fixture data from the Phase 0 reports:

```bash
PYTHONPATH=src .venv310/bin/python tools/build_phase1_fixtures.py
```

Run the deterministic fixture-backed scoring API:

```bash
GITAI_DATA_DIR=data/scoring \
GITAI_MODEL=heuristic \
GITAI_OCR=fingerprint \
HF_HOME=.cache/huggingface \
TORCH_HOME=.cache/torch \
XDG_CACHE_HOME=.cache/xdg \
.venv310/bin/python -m uvicorn gitai_phase0.server:app --host 127.0.0.1 --port 8000
```

The service exposes:

- `GET /healthz`
- `POST /v1/score`
- `POST /v1/submissions`
- `GET /v1/leaderboard`
- `GET /v1/ghost`
- `POST /v1/funny-votes`
- `POST /v1/appraisal-comments`
- `POST /v1/pair-proposals`
- `GET /v1/pair-proposals`
- `POST /v1/pair-proposals/{proposal_id}/review`
- `GET /v1/pair-seed-queue`
- `GET /v1/share-card`

`POST /v1/score` expects `{ image_b64, pair_id, ref_version, stroke_log? }` and
returns the Phase 1 response shape: score, percentile, raw, confidences, bucket,
flags, model version, template set, tau, timestamp, and a template-bank
`comment` for the appraiser reveal.

`POST /v1/submissions` accepts the same drawing payload plus
`{ puzzle_date?, user_id, display_name, friend_code? }`, persists a scored submission, and
returns the score with `submission_id` and current daily rank. `GET
/v1/leaderboard?date=YYYY-MM-DD&kind=score` returns the score ranking.
`kind=efficiency` returns a separate ladder for `fooled` submissions ordered by
fewest strokes. `kind=friend&friend_code=ABC123` returns the score ladder for
only that invite code. `kind=funny` returns the human-voted ladder, sorted by
unique funny votes and then score.

Ranked submissions replay `stroke_log` server-side before saving. If the
submitted PNG is too far from the replayed drawing, the API returns `422` and
does not add it to the leaderboard.

Public leaderboards and ghosts only include submissions that pass moderation
and are not OCR text cheats. Bursty ranked actions are rate limited; `429`
responses include `Retry-After`.

Local image moderation is deterministic and fixture-driven by default:

```bash
GITAI_MODERATION=fingerprint  # reads data/scoring/moderation_fixtures.json
GITAI_MODERATION=none         # development-only bypass
```

`GET /v1/ghost?date=YYYY-MM-DD&kind=score` returns the current #1 submission
with its PNG as `image_b64` and the stored `stroke_log`, so the client can show
and replay "beat this" without realtime play. Seed ghosts are generated from the
same replayable stroke-log format, so fresh leaderboards can still show a
replay target before any player has submitted. Use `kind=efficiency` to show the
top efficient ghost, or
`kind=friend&friend_code=ABC123` to show the top ghost in a private circle.
`kind=funny` shows the current most-voted ghost.

`POST /v1/funny-votes` accepts `{ submission_id, user_id }`. Votes are unique
per `(submission_id, user_id)` and players cannot vote for their own submission.

`POST /v1/appraisal-comments` accepts `{ submission_id, user_id }` and tries to
mint a higher-cost appraiser comment. If Layer2 is unavailable, unsafe, over
the user's free quota, or over the daily spend cap, it returns the template-bank
comment instead. The response includes `status`, `daily_spend`, `daily_cap`, and
`user_remaining`.

The same endpoint accepts `mode: "hero"` for high-percentile automatic minting.
Hero mode is allowed only for safe submissions with `percentile >= 0.95`,
`moderation=pass`, and no OCR cheat. It still obeys the daily spend cap but does
not consume the player's on-demand daily quota.

Ranked submissions can be capped per player per daily puzzle:

```bash
GITAI_DAILY_SUBMISSION_LIMIT=10 \
GITAI_PREMIUM_USER_IDS=local-player,founder-account \
npm run dev:api:fast
```

Premium user ids bypass the daily submission cap. Burst rate limits still apply.
You can also seed server-authoritative premium pass codes:

```bash
GITAI_PREMIUM_REDEEM_CODES=FOUNDERS:100 \
npm run dev:api:fast
```

Players can redeem a code from the Pass control in the app, or call
`POST /v1/premium/redeem` with `{ user_id, code }`. `GET /v1/premium?user_id=...`
returns the current pass state.

Players can also suggest future DailyPuzzle pairs from the `Next Pair` control,
or by calling `POST /v1/pair-proposals` with
`{ user_id, base_label, target_label }`. Known catalog pairs that pass the
shape plausibility gate are stored as `candidate`; unknown labels are kept as
`needs_catalog_review`; invalid same-object or implausible pairs are stored as
`rejected`. Duplicate suggestions are aggregated into one proposal and increase
`support_count`, so operators can inspect the strongest candidate queue with
`GET /v1/pair-proposals?status=candidate`. Operators can approve a known-object
proposal for the seed-generation queue or reject it with
`POST /v1/pair-proposals/{proposal_id}/review` and
`{ reviewer_id, status: "approved"|"needs_catalog_review"|"rejected", note? }`.
Approved proposals are available as frozen seed-generation candidates from
`GET /v1/pair-seed-queue`.

Cosmetic rewards are server-authoritative and score-neutral. Safe ranked
submissions unlock palette cosmetics at score milestones, and clients can fetch
the current unlock list with:

```text
GET /v1/cosmetics?user_id=local-player&season_id=season-1
```

Cosmetics never change scoring, ranking, or moderation.

Seasons scope ranked submissions and pin the scoring model:

```bash
GITAI_SEASON_ID=season-1 \
GITAI_SEASON_LABEL="Season 1" \
GITAI_SEASON_MODEL_VERSION=heuristic-color-shape-v1 \
npm run dev:api:fast
```

Changing `GITAI_SEASON_ID` resets public leaderboards without deleting old
submissions. If `GITAI_SEASON_MODEL_VERSION` does not match the active judge,
the API refuses to start so a season cannot silently drift models.

Write a read-only season operations report after a playtest or season cut:

```bash
PYTHONPATH=src .venv310/bin/python tools/report_phase5_season_ops.py \
  --runtime-db data/runtime/play.sqlite \
  --season-id season-1 \
  --season-label "Season 1" \
  --season-model-version heuristic-color-shape-v1
```

The report is written to `reports/phase5/season_ops_<season-id>.json` and `.md`.
It summarizes model pin health, public/safety-filtered submissions, Layer2 spend,
cosmetic unlocks, premium pass activity, and rescore candidates.

Simulate the Phase 5 budget gate:

```bash
PYTHONPATH=src .venv310/bin/python tools/smoke_phase5_budget.py \
  --requests 25 \
  --daily-cap-units 5
```

This writes `reports/phase5/phase5_budget_smoke.json` and `.md`. The smoke
passes only when Layer2 spend stays within the daily cap and later requests
fall back instead of minting paid comments.

`GET /v1/share-card?submission_id=...` returns a generated 9:16 PNG for a
shareable submission. OCR-cheat or moderation-failed submissions are not
cardable.

Run an API smoke check without starting a server:

```bash
GITAI_DATA_DIR=data/scoring \
GITAI_MODEL=open_clip \
GITAI_OCR=fingerprint \
HF_HOME=.cache/huggingface \
TORCH_HOME=.cache/torch \
XDG_CACHE_HOME=.cache/xdg \
.venv310/bin/python tools/smoke_phase1_api.py
```

## Phase 2 puzzle pool

Build the local ObjectCatalog funnel and measured quality report:

```bash
PYTHONPATH=src .venv310/bin/python tools/build_phase2_puzzle_pool.py
```

Outputs:

- `data/puzzle/pair_candidates.json`
- `data/puzzle/measured_quality.json`
- `data/puzzle/daily_puzzles.json`
- `reports/phase2_puzzle_pool.md`

The checked-in playtest pack has an 8-day heuristic DailyPuzzle schedule so the
local game can rotate prompts without real model cost:

```bash
PYTHONPATH=src .venv310/bin/python tools/validate_phase2_playtest_pack.py
```

This writes `reports/phase2/playtest_pack.json` and `.md`. The real Phase 2
gate still needs dozens of real-model measured pairs before committing
generation budget; the heuristic pack is for local playability and UX testing.

Export operator-approved player suggestions as the next seed-generation queue:

```bash
PYTHONPATH=src .venv310/bin/python tools/export_approved_pair_seed_queue.py \
  --runtime-db data/runtime/play.sqlite
```

This writes `reports/phase2/approved_pair_seed_queue.json` and `.md`.

Build deterministic local SeedAsset fixtures from the approved queue:

```bash
PYTHONPATH=src .venv310/bin/python tools/build_approved_seed_asset_pack.py \
  --runtime-db data/runtime/play.sqlite
```

This writes PNG seed assets plus `approved_seed_assets.json`,
`approved_seed_cases.json`, `approved_seed_pairs.json`, and a Markdown summary
under `data/puzzle/approved_seed_asset_pack/`. The local renderer is a
drop-in stand-in for the later paid image-generation adapter.

Score that SeedAsset pack into draft SeedScores and measured quality:

```bash
PYTHONPATH=src .venv310/bin/python tools/score_approved_seed_asset_pack.py \
  --cases data/puzzle/approved_seed_asset_pack/approved_seed_cases.json \
  --images-root data/puzzle/approved_seed_asset_pack \
  --model heuristic
```

This writes `approved_seed_scores.json`, `approved_measured_quality.json`,
`approved_seed_score_results.json`, and a Markdown report under
`reports/phase2/approved_seed_scores/`.

Preview or apply accepted draft SeedScores into the canonical scoring data:

```bash
PYTHONPATH=src .venv310/bin/python tools/promote_approved_seed_scores.py \
  --draft-pairs data/puzzle/approved_seed_asset_pack/approved_seed_pairs.json \
  --draft-seed-scores reports/phase2/approved_seed_scores/approved_seed_scores.json \
  --measured-quality reports/phase2/approved_seed_scores/approved_measured_quality.json
```

The command writes a promotion report and merged preview under
`reports/phase2/seed_score_promotion/`. Add `--apply` only after reviewing the
report; rejected quality rows are skipped unless `--allow-rejected` is set.

Plan upcoming DailyPuzzle entries from accepted promoted SeedScores:

```bash
PYTHONPATH=src .venv310/bin/python tools/plan_daily_puzzles_from_seed_scores.py \
  --seed-scores reports/phase2/seed_score_promotion/merged_seed_scores.json
```

The planner writes a merged preview and report under
`reports/phase2/daily_puzzle_plan/`. Existing pair_ids are skipped by default;
use `--allow-repeat-pairs` only when deliberately re-running a pair with a new
ref. Add `--apply` after reviewing the report to write
`data/puzzle/daily_puzzles.json`.

Draft review rows for new catalog objects:

```bash
PYTHONPATH=src .venv310/bin/python tools/tag_objects.py \
  --labels path/to/labels.txt \
  --out data/puzzle/object_review.csv
```

## Phase 3 playable loop

Install frontend dependencies with the project-local npm cache:

```bash
npm install --cache .cache/npm
```

Start the real-model scoring API:

```bash
npm run dev:api
```

In another terminal, start the web client:

```bash
npm run dev:web
```

Open:

```text
http://127.0.0.1:5173/
```

If Vite falls back to `5174` because `5173` is already in use, the API default
CORS settings allow that local origin too.

The playable loop is:

```text
Daily picker -> draw on Canvas2D -> replay strokes -> submit to /v1/submissions -> reveal verdict -> daily ranking -> generated share card
```

`GET /v1/daily-puzzles` lists available DailyPuzzle entries up to today.
`GET /v1/daily-puzzle?date=YYYY-MM-DD` fetches a specific available frozen
entry. Future DailyPuzzle entries stay hidden from the player-facing API.

For a faster local-only loop, use the heuristic API instead:

```bash
npm run dev:api:fast
```

The fast mode uses the checked-in heuristic DailyPuzzle refs, so the 8-day
playtest pack can rotate prompts without real model cost. The real-model path
uses a same-pair seed ref for the active judge model when one is available. If a
DailyPuzzle has no compatible ref for the active judge, the API returns `404`
instead of silently scoring against the wrong model. In the checked-in local
pack, `apple -> baseball` has OpenCLIP/SigLIP refs; the other seven days are
heuristic-only playtest content.

## Phase 4 async competition loop

The local competition store uses SQLite and defaults to:

```text
data/runtime/gitai.sqlite
```

Seed ghosts are loaded from `data/competition/seed_ghosts.json` at API startup
and inserted once into the local store. This keeps a fresh daily leaderboard
from starting empty.

Rebuild and validate the local seed ghost pack after changing DailyPuzzle data:

```bash
PYTHONPATH=src .venv310/bin/python tools/build_seed_ghost_pack.py
PYTHONPATH=src .venv310/bin/python tools/validate_phase4_seed_ghosts.py
```

The validator writes `reports/phase4/seed_ghosts.json` and `.md`, and checks
that every DailyPuzzle has both score and efficiency ghosts, image files, and
stroke logs that replay back to the stored PNGs.

For a reviewable release candidate from the approved-seed pipeline, build the
ghost pack against the planner preview before applying DailyPuzzle changes:

```bash
PYTHONPATH=src .venv310/bin/python tools/build_seed_ghost_pack.py \
  --daily-puzzles reports/phase2/daily_puzzle_plan/merged_daily_puzzles.json \
  --pairs reports/phase2/seed_score_promotion/merged_pairs.json \
  --seed-scores reports/phase2/seed_score_promotion/merged_seed_scores.json \
  --out-dir reports/phase4/planned_seed_ghost_images \
  --out-json reports/phase4/planned_seed_ghosts.json

PYTHONPATH=src .venv310/bin/python tools/validate_phase4_seed_ghosts.py \
  --daily-puzzles reports/phase2/daily_puzzle_plan/merged_daily_puzzles.json \
  --pairs reports/phase2/seed_score_promotion/merged_pairs.json \
  --seed-ghosts reports/phase4/planned_seed_ghosts.json \
  --out-dir reports/phase4/planned_seed_ghosts \
  --season-id season-1
```

Validate the whole release candidate bundle before moving any preview files into
canonical locations:

```bash
PYTHONPATH=src .venv310/bin/python tools/validate_release_candidate.py \
  --promotion-report reports/phase2/seed_score_promotion/promotion_report.json \
  --daily-plan-report reports/phase2/daily_puzzle_plan/daily_puzzle_plan.json \
  --pairs reports/phase2/seed_score_promotion/merged_pairs.json \
  --seed-scores reports/phase2/seed_score_promotion/merged_seed_scores.json \
  --daily-puzzles reports/phase2/daily_puzzle_plan/merged_daily_puzzles.json \
  --seed-ghosts reports/phase4/planned_seed_ghosts.json \
  --out-dir reports/release_candidate \
  --season-id season-1
```

The release candidate report checks promotion errors, DailyPuzzle plan errors,
pair/ref linkage, unique DailyPuzzle dates, and full replayable seed ghost
coverage. It also writes the API preview environment block to
`release_candidate.md`.

Preview the canonical write plan after the release candidate validates:

```bash
PYTHONPATH=src .venv310/bin/python tools/apply_release_candidate.py \
  --promotion-report reports/phase2/seed_score_promotion/promotion_report.json \
  --daily-plan-report reports/phase2/daily_puzzle_plan/daily_puzzle_plan.json \
  --pairs reports/phase2/seed_score_promotion/merged_pairs.json \
  --seed-scores reports/phase2/seed_score_promotion/merged_seed_scores.json \
  --daily-puzzles reports/phase2/daily_puzzle_plan/merged_daily_puzzles.json \
  --seed-ghosts reports/phase4/planned_seed_ghosts.json \
  --out-dir reports/release_candidate_apply \
  --season-id season-1
```

Add `--apply` only after the dry-run report is reviewed. The apply step writes
canonical scoring data, DailyPuzzle data, seed ghosts, and seed ghost images,
with backups under `reports/release_candidate_apply/backup/`.

Preview a rollback from an applied release report:

```bash
PYTHONPATH=src .venv310/bin/python tools/rollback_release_candidate.py \
  --apply-report reports/release_candidate_apply/apply_release_candidate.json \
  --out-dir reports/release_candidate_rollback
```

Add `--apply` to restore backed-up canonical files and remove newly-created seed
ghost images that had no prior backup.

Run a read-only release readiness smoke after applying or previewing a pack:

```bash
PYTHONPATH=src .venv310/bin/python tools/smoke_release_readiness.py
```

This writes `reports/release_readiness/release_readiness.json` and `.md`. It
checks canonical pair/ref linkage, DailyPuzzle uniqueness, seed ghost coverage,
release candidate validation, rollback dry-run readiness, built web assets, and
the latest DailyPuzzle API path with seeded ghosts, deterministic scoring, and
a first-player flow through submit, leaderboard, share card, funny vote,
appraiser comment fallback, premium redeem, and pair proposal. It also runs the
Phase 5 Layer2 budget smoke, so release readiness fails if paid appraiser
comment minting can exceed the daily cap instead of degrading to templates.

You can run that first-player flow directly when working on the playable loop:

```bash
PYTHONPATH=src .venv310/bin/python tools/smoke_first_play_api.py
```

It writes `reports/first_play_api/first_play_api.json` and `.md` using a
temporary runtime database, so canonical data and local playtest records are not
modified.

Run the local API against that preview without moving files into canonical
locations:

```bash
GITAI_PAIRS_PATH=reports/phase2/seed_score_promotion/merged_pairs.json \
GITAI_SEED_SCORES_PATH=reports/phase2/seed_score_promotion/merged_seed_scores.json \
GITAI_DAILY_PUZZLES_PATH=reports/phase2/daily_puzzle_plan/merged_daily_puzzles.json \
GITAI_SEED_GHOSTS=reports/phase4/planned_seed_ghosts.json \
GITAI_TODAY=2026-07-06 \
npm run dev:api:fast
```

Player submission images are saved under `data/runtime/submissions` by default.

Override it with `GITAI_RUNTIME_DB` when running multiple local environments:

```bash
GITAI_RUNTIME_DB=data/runtime/dev.sqlite npm run dev:api:fast
```

Tune the stroke replay tolerance with `GITAI_REPLAY_MAX_ERROR` if browser
rendering differences need calibration. The default is `0.08`.

The web client keeps a local player id and friend circle code in browser
storage, sends both with each submission, and refreshes the leaderboard after
every verdict. Invite links can include `?circle=ABC123`; the client opens
directly on the Friends ladder for that code.

The Replay control replays the current stroke log from the frozen base object.
During replay and scoring, drawing controls are locked so the submitted PNG and
stroke log cannot drift apart mid-verdict.

## Web publishing and marketing assets

The web entrypoint includes production-facing metadata for search/social cards,
PWA install metadata, and brand icons:

- Open Graph image: `web/public/brand/og-image.png`
- 16:9 marketing hero: `web/public/brand/marketing-hero-16x9.png`
- PWA icons: `web/public/brand/app-icon-192.png`, `web/public/brand/app-icon-512.png`
- Touch/favicon assets: `web/public/brand/apple-touch-icon.png`, `web/public/brand/favicon-32.png`
- Web manifest: `web/public/site.webmanifest`

The launch plan and generated-asset inventory live under `docs/marketing/`.
Run `npm run check` and `tools/smoke_phase3_static.py` after changing metadata
or brand assets; the static smoke verifies that the built app still contains the
publish metadata and copied public assets. Production builds default to
same-origin API requests; set `VITE_GITAI_API_BASE` only when the API is hosted
on a separate origin. API deployments should set `GITAI_PUBLIC_WEB_URL` so share
cards point at the public app instead of showing the fallback `gitai` footer.
See `docs/deployment.md` for the deploy preflight.

Run the public launch audit after a production build:

```bash
PYTHONPATH=src .venv310/bin/python tools/smoke_public_launch.py
PYTHONPATH=src .venv310/bin/python tools/audit_launch_package.py
```

The public smoke verifies launch metadata, brand asset dimensions, PWA manifest
basics, same-origin serving, and the absence of localhost API defaults in the
production bundle. Validate `.env.production` with
`tools/validate_production_env.py` before deploying; the checked-in example
should only be run with `--allow-placeholders`. Use
`tools/audit_real_model_pair_coverage.py` to keep the real-model pair expansion
backlog visible. The launch package audit then gathers release readiness,
first-play flow, static smoke, production env template health, real-model
coverage backlog, policy pages, marketing docs, and imagegen assets into
`reports/launch_package_audit/`. Manual follow-ups such as real production
origins and outside playtest metrics are reported separately.

## Phase 5 appraiser comments

`src/gitai_phase0/commentary.py` provides the zero-cost template bank for the
appraiser persona. It never changes scoring authority: it only turns an already
computed verdict into `{ line, mood, source, template_id }`. The web reveal and
share card use the same comment path so the card matches the in-app verdict.

Layer2 comment minting is guarded by a hard daily budget. Configure it with:

```bash
GITAI_DAILY_LLM_SPEND_CAP=100 GITAI_USER_DAILY_COMMENT_LIMIT=3 npm run dev:api:fast
```

The default local actor is disabled, so no external LLM call is made unless a
real actor is selected.

Actor selection is environment-driven:

```bash
# default: no external call
GITAI_LAYER2_ACTOR=null

# local development: deterministic generated comment, with optional template fields
GITAI_LAYER2_ACTOR=scripted \
GITAI_LAYER2_SCRIPTED_LINE='これは由緒ある{target}です。' \
GITAI_LAYER2_SCRIPTED_MOOD=smug \
GITAI_LAYER2_SCRIPTED_COST_UNITS=1 \
npm run dev:api:fast

# provider-agnostic HTTP adapter
GITAI_LAYER2_ACTOR=http \
GITAI_LAYER2_HTTP_URL=https://example.internal/appraise \
GITAI_LAYER2_HTTP_TOKEN=optional-bearer-token \
GITAI_LAYER2_HTTP_TIMEOUT=10 \
GITAI_LAYER2_HTTP_COST_UNITS=1 \
npm run dev:api:fast
```

The HTTP adapter sends `{ system, user, image_b64 }` as JSON and accepts either
`{ line, mood }`, `{ comment: { line, mood } }`, or `{ text: "{\"line\":...}" }`.
It does not depend on a specific model vendor; the app keeps the budget ledger,
cache, and final safety gate locally.

Layer2 output must pass the local JSON parser and safety filter before it can be
cached. The filter rejects malformed JSON, unsupported moods, person-directed
insults, links, and overly long lines; rejected output still counts against the
daily spend ledger so retries cannot bypass the cap.

Check frontend and backend:

```bash
npm run check
PYTHONPATH=src .venv310/bin/python tools/smoke_phase3_static.py
HF_HOME=.cache/huggingface TORCH_HOME=.cache/torch XDG_CACHE_HOME=.cache/xdg .venv310/bin/python -m pytest
```

## Real model adapters

The adapters are intentionally optional because model packages and weights may
need network access:

```bash
python3 -m pip install -e ".[clip]"
PYTHONPATH=src python3 -m gitai_phase0 run --model open_clip
```

```bash
python3 -m pip install -e ".[siglip]"
PYTHONPATH=src python3 -m gitai_phase0 run --model siglip
```

Both adapters keep the same scoring path: fixed image encoding, drawing-domain
text template ensemble, temperature softmax, `raw = Cy * (1 - Cx)`, then OCR
hard-zeroing for target or hard-negative text.
