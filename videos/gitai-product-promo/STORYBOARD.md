# Storyboard

**Format:** 1920x1080  
**Audio:** System TTS voiceover + subtle UI SFX implied in motion  
**VO direction:** calm, confident, lightly playful; leave small pauses after "Draw. Submit." and "gitai."  
**Style basis:** DESIGN.md, using exact captured colors and UI components.

## Asset Audit

| Asset | Type | Assign to Beat | Role |
| --- | --- | --- | --- |
| `capture/screenshots/scroll-000.png` | App screenshot | Beat 1, Beat 3 | Full interface proof and leaderboard context |
| `capture/screenshots/scroll-001.png` | App screenshot | Beat 2 | Lower workbench/tool dock detail |
| `capture/screenshots/full-page.png` | App screenshot | Beat 3 | Background interface layer |
| `capture/assets/top-ghost.png` | Drawing asset | Beat 1, Beat 3 | Proof that the apple was transformed into baseball |
| `capture/assets/top-ghost-proof.png` | Drawing asset | Beat 3 | Separate proof-panel copy of the top ghost drawing |
| `capture/assets/share-card-seed.png` | Share artifact | Beat 4 | Final social output and CTA |

## BEAT 1 - The Challenge (0.00-4.80s)

**VO:** "In gitai, the prompt is simple: turn apple into baseball."

**Concept:** The viewer lands directly inside today's challenge. The app screenshot is present as a real workbench, but the daily prompt is lifted out like a game card: apple on one side, baseball on the other, red arrow between them. The top ghost baseball floats nearby as proof that the transformation is possible.

**Visual:** A cream paper background fills the frame. The captured app screenshot sits as a large angled panel in the background with a gentle zoom. In the foreground, two rounded tiles stamp in: `apple` and `baseball`, connected by a drawn red arrow. A circular baseball ghost slides into the right edge while tiny rank/date chips orbit the prompt.

**Mood direction:** board-game table meets clean product reveal; tactile, immediate, not tech demo.

**Assets:** `scroll-000.png` as background workbench, `top-ghost.png` as proof object.

**Animation choreography:** screenshot floats in with perspective tilt; object tiles stamp down; arrow draws itself; ghost ball drifts in; small metadata chips count on.

**Transition:** warm green wipe sweeps left-to-right over the frame.

**Depth layers:** BG paper texture and screenshot; MG prompt tiles; FG arrow stroke, ghost ball, date chip.

**SFX cues:** soft paper stamp on object tiles, quick pen stroke on the arrow.

## BEAT 2 - Draw, Then Submit (4.80-9.80s)

**VO:** "Draw. Submit."

**Concept:** This beat is about agency and speed. The captured workbench becomes a kinetic drawing station: brush tools, swatches, and the submit button all snap into focus while red baseball seams draw over the apple.

**Visual:** The canvas area from the app fills the center. A simplified apple silhouette sits on a white drawing card; red seam paths sketch themselves over it, then the card tilts forward like a submitted entry. Tool icons and color swatches cascade up from the bottom strip.

**Mood direction:** satisfying craft loop; fast but readable.

**Assets:** `scroll-001.png` as tool/workbench reference; vector apple and seam paths recreated in CSS/SVG from the app style.

**Animation choreography:** toolbar buttons cascade; seam SVG paths draw; submit button pulses green; scan line sweeps across the canvas; the whole drawing card nudges forward.

**Transition:** beige paper slide upward into the scoring rail.

**Depth layers:** BG lower screenshot; MG white canvas card; FG seam paths, scan line, tool chips.

**SFX cues:** two crisp taps for "Draw. Submit.", then a scanner sweep.

## BEAT 3 - Deterministic Judge (9.80-15.00s)

**VO:** "The judge is a deterministic vision model, not vibes. Fool it, climb the daily board,"

**Concept:** The promo pivots from playful drawing to trustworthy competition. The verdict rail and leaderboard become the hero: numbers count up, ranks slide into place, and the judge diamond locks onto `1000`.

**Visual:** The app interface sits full-width in the background, softened but recognizable. A foreground verdict panel assembles with confidence tiles and a huge `1000`. Leaderboard rows stack in from below: Seed Ghost at the top, then competing entries. The top ghost baseball sits inside a framed preview, linking the drawing to the score.

**Mood direction:** measured, auditable, competitive.

**Assets:** `full-page.png`, `scroll-000.png`, `top-ghost.png`.

**Animation choreography:** score counts from 0 to 1000; confidence bars fill; leaderboard rows slide and settle; judge diamond rotates once; ghost preview breathes subtly.

**Transition:** green result block expands until it becomes the share-card background.

**Depth layers:** BG interface screenshot; MG verdict panel and leaderboard; FG score counter and judge mark.

**SFX cues:** soft counter ticks, one clean chime when score hits 1000.

## BEAT 4 - Share The Trick (15.00-20.00s)

**VO:** "and ship a share card your friends instantly understand. gitai. Make the AI believe."

**Concept:** The product loop resolves into a social artifact. The tall share card stands upright in the center and becomes the CTA: it already contains the joke, the puzzle, the score, and the challenge link.

**Visual:** `share-card-seed.png` rises from below in a subtle device-like frame. Behind it, oversized low-opacity words "DRAW", "FOOL", and "SHARE" drift across the paper background. The final `gitai` wordmark appears on the left, with a green CTA pill reading "Make the AI believe."

**Mood direction:** crisp finish, social-ready, playful confidence.

**Assets:** `share-card-seed.png`.

**Animation choreography:** share card rises and gently scales; ghost words drift; CTA pill fills green; final wordmark locks into place; final scene fades only in the last half-second.

**Transition:** final fade to paper white.

**Depth layers:** BG paper and ghost words; MG portrait share card; FG wordmark and CTA.

**SFX cues:** camera-card lift, low final chord.

## Production Architecture

```text
project/
├── index.html
├── DESIGN.md
├── SCRIPT.md
├── STORYBOARD.md
├── narration.txt
├── narration.wav
├── transcript.json
├── capture/
│   ├── screenshots/
│   ├── assets/
│   └── extracted/
└── snapshots/
```
