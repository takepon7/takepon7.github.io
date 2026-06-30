# gitai Marketing Plan

## Positioning

gitai is a fast, shareable web game where players draw over a clear base object and try to make an AI judge confidently mistake it for the target. The hook is not "draw well"; it is "make the machine believe the disguise."

Primary promise:

- Draw a disguise.
- Fool the AI.
- Share the ridiculous verdict.

Core audience:

- Casual puzzle and drawing-game players.
- AI-curious social users who enjoy "can you beat the model?" challenges.
- Streamers and short-form creators who need quick visual payoffs.

## Launch Thesis

The product should launch around one repeatable daily ritual:

> Today's disguise: turn X into Y. Can you fool the appraiser better than your friends?

Growth should depend on share cards, friend circles, and ghost replays instead of real-time multiplayer. This keeps cost and infrastructure risk controlled while still giving every player a visible opponent.

## Funnel

Awareness:

- Short clips showing the before canvas, a strange disguise, and the appraiser confidently naming the wrong object.
- Static image posts using the generated key visual and a score/share-card mock.
- Daily prompt posts: "Today: apple -> baseball. Show us your fake."

Activation:

- First screen is the playable canvas, not a landing page.
- The share card appears immediately after a valid submission.
- Fresh leaderboards are seeded with replayable ghosts so the first user has a target.

Retention:

- Daily puzzle schedule.
- Friend-circle links.
- Efficiency ladder for "fewest strokes" meta play.
- Funny ladder for failures worth sharing.
- Season resets when the model changes.

Revenue:

- Premium pass: more daily attempts, ad-free path, more on-demand appraiser comments, cosmetics.
- Keep all rewards cosmetic and score-neutral.
- Layer2 appraiser comments remain budget-capped and gracefully fall back to templates.

## Channel Plan

Week -2 to -1: Closed Playtest

- Recruit 20-50 testers from AI/game/dev communities.
- Measure: first submission rate, share-card click rate, second attempt rate.
- Collect 10-20 funny examples for launch posts.

Launch Week

- Daily X -> Y challenge post for 7 days.
- Pin one "how it works in 10 seconds" clip.
- Share a leaderboard screenshot and one funny failed attempt each day.
- Ask players to reply with screenshots rather than only link clicks.

Post Launch

- Theme weeks: food, tools, vehicles, "round things".
- Community pair proposal voting using the in-app proposal flow.
- Creator challenge: "beat this ghost in 3 strokes."

## Creative Direction

Visual tone:

- Premium museum x messy drawing desk.
- Confident appraiser persona, never mean to the player.
- The joke is the verdict, not the player's skill.

Copy examples:

- "AIをだませ。鑑定士を黙らせるな、信じ込ませろ。"
- "今日のお題: りんごを野球ボールに化けさせる。"
- "うまい絵より、信じられる嘘。"
- "あなたの落書き、AIには名品かもしれない。"

## Required Assets

Generated and checked in:

- Web/Open Graph key visual: `web/public/brand/og-image.png`
- 16:9 marketing hero: `web/public/brand/marketing-hero-16x9.png`
- Square social feed creative: `web/public/brand/social-feed-square.png`
- Vertical story/reel cover creative: `web/public/brand/social-story-vertical.png`
- Five generated share-card examples: `web/public/brand/share-cards/*.png`
- PWA icons: `web/public/brand/app-icon-192.png`, `web/public/brand/app-icon-512.png`
- Apple touch icon: `web/public/brand/apple-touch-icon.png`
- Favicon: `web/public/brand/favicon-32.png`

Still useful before a public launch:

- Three real gameplay clips, 8-12 seconds each.
- One creator/press one-pager PDF/layout built from the checked-in press one-pager and screenshots.

## KPIs

- First submission completion rate.
- Attempts per daily active user.
- Share-card generation rate.
- Friend-circle join rate.
- Day-2 return rate.
- Layer2 spend per 1,000 submissions.
- Moderation flag rate.

## Launch Gate

Do not call the launch ready until these are true:

- `npm run check` passes.
- `tools/smoke_release_readiness.py` is valid.
- Latest daily puzzle is playable end to end.
- Share card and OG metadata resolve in production.
- Budget smoke proves Layer2 comments cannot exceed the daily cap.
- At least 20 outside testers have completed a submission.
