# gitai Press One-Pager

## One-Line Pitch

gitai is a browser drawing game where players disguise an object and try to make an AI appraiser confidently mistake it for the target.

## What It Is

Players start from a visible base object, draw a disguise on top of it, and submit the canvas for appraisal. The game scores how convincingly the model reads the drawing as the target object, then turns the result into a shareable card with a playful appraiser comment.

## Why It Is Different

- The goal is not beautiful drawing; the goal is a believable visual trick.
- Every daily puzzle is instantly understandable as "turn X into Y."
- Ghost replays give first-time players a target even before live leaderboards are crowded.
- Friend circles support small social competitions without real-time multiplayer complexity.
- Layer2 appraiser comments are capped by budget controls and degrade to templates when needed.

## Launch Positioning

Primary hook:

> Draw a disguise. Fool the AI. Share the ridiculous verdict.

Launch ritual:

> Today's disguise: turn X into Y. Can you fool the appraiser better than your friends?

## Audience

- Casual web game players.
- AI-curious social users.
- Streamers and short-form creators looking for fast visual outcomes.
- Drawing-game fans who enjoy low-pressure challenges.

## Key Features

- Daily disguise puzzles.
- Score, efficiency, friends, and funny leaderboards.
- Replayable ghost drawings.
- Share cards with percentile and appraiser comments.
- Premium-safe cosmetic rewards and comment limits.
- Pair proposal flow for future community prompts.

## Asset Links

- Open Graph image: `web/public/brand/og-image.png`
- 16:9 hero: `web/public/brand/marketing-hero-16x9.png`
- Square social creative: `web/public/brand/social-feed-square.png`
- Vertical story creative: `web/public/brand/social-story-vertical.png`
- App icon: `web/public/brand/app-icon-512.png`

## Launch Readiness Notes

Automated release checks currently verify the production bundle, metadata, share surfaces, seed ghosts, replayable drawings, public assets, and Layer2 budget gate. Before a serious public push, complete an external playtest with at least 20 players and set production `GITAI_CORS_ORIGINS` and `GITAI_PUBLIC_WEB_URL`.
