# Design System

## Overview

gitai is a warm, utilitarian drawing-game interface with a tabletop feel. The layout is a dense three-panel workbench: daily puzzle briefing on the left, large drawing canvas in the center, verdict, ranking, and share output on the right. The visual identity relies on paper-cream surfaces, thin beige borders, heavy black type, and small red/green game signals. It feels closer to a compact board-game tool than a glossy SaaS landing page.

## Colors

- **Ink Text**: `#181716` — primary text, large scores, and UI icons.
- **Paper Surface**: `#FFFDF7` — main panel and topbar background.
- **Workbench Ground**: `#EEE4D4` — warm canvas area behind the drawing card.
- **Border Quiet**: `#DDD6C8` — primary 1px panel dividers.
- **Border Strong**: `#CFC5B4` — inputs, cards, and framed controls.
- **Label Text**: `#776F65` — uppercase metadata labels.
- **Transform Red**: `#8B4538` — arrow, rank markers, and misdirection emphasis.
- **Share Green**: `#244F43` — result/share-card accent and final CTA field.
- **Soft Tile**: `#F8F2E8` — puzzle object tiles and stat cards.
- **White Canvas**: `#FFFFFF` — drawing and asset preview fields.

## Typography

- **Primary Sans**: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif.
- **Weights**: 400 for body/UI content, 700 for labels and controls, 800 for object names and headings, 900 for scores and rank emphasis.
- **Hierarchy**: tiny uppercase labels at 12px in the app; promo can scale these labels to 18-24px while preserving uppercase treatment. Headlines should stay blunt and compact, with no negative letter spacing.
- **Numerals**: use tabular numerals for scores, dates, ranks, and confidence readouts.

## Elevation

Depth is made with thin borders, off-white panels, and faint warm shadows rather than dramatic drop shadows. Canvas and share-card surfaces sit inside framed rectangles with 8px radius or less. The captured app uses flat color shifts for hierarchy: paper panels over a warmer ground, white drawing fields inside paper panels, and green result blocks for social output.

## Components

- **Daily Transformation Header**: two rounded object tiles connected by a red arrow, showing the base object becoming the target.
- **Drawing Workbench**: large white canvas card centered in a warm beige stage, framed by a compact title row and action row.
- **Tool Dock**: square icon controls, color swatches, and a brush-size slider in a dense bottom control strip.
- **Verdict Rail**: right-side score/judge column with a black diamond judge face, confidence tiles, and status text.
- **Leaderboard Stack**: compact ordered list with rank, name, score, and stroke count, plus segmented tabs.
- **Share Card**: tall portrait social artifact with black header, large drawing preview, green score block, and Japanese CTA.

## Do's and Don'ts

### Do's

- Use `#FFFDF7`, `#EEE4D4`, and `#FFFFFF` as the dominant surfaces.
- Keep borders visible and thin with `#DDD6C8` or `#CFC5B4`.
- Let red and green act as game signals, not decorative washes.
- Use real captured screenshots and generated share-card imagery prominently.
- Keep UI dense, legible, and repeat-play focused.

### Don'ts

- Do not switch into dark neon tech styling; the app is warm and paper-like.
- Do not use large rounded cards beyond the app's 8px radius language.
- Do not invent purple/blue gradients or glassmorphism.
- Do not make empty text-only beats; the game loop needs visible drawing, score, and share artifacts.
- Do not hide the product behind atmospheric crops; show the actual interface and output.
