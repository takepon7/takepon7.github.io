# Marketing Asset Manifest

## Generated With Imagegen

Built-in `image_gen` mode was used for the project-bound raster assets.

### Key Visual

- Source: `web/public/brand/gitai-key-visual.png`
- Derived:
  - `web/public/brand/og-image.png` - 1200x630 Open Graph image
  - `web/public/brand/marketing-hero-16x9.png` - 1600x900 launch hero
- Prompt summary: premium gallery/game key visual with an apple disguised as a baseball and an overconfident appraiser, no image text.

### App Icon

- Source: `web/public/brand/gitai-app-icon-source.png`
- Derived:
  - `web/public/brand/app-icon-512.png`
  - `web/public/brand/app-icon-192.png`
  - `web/public/brand/apple-touch-icon.png`
  - `web/public/brand/favicon-32.png`
- Prompt summary: square premium icon of an apple painted as a baseball with a gold loupe motif, no text.

### Social Launch Creatives

- Feed source: `web/public/brand/social-feed-square-source.png`
- Feed derived:
  - `web/public/brand/social-feed-square.png` - 1080x1080 feed creative
- Story source: `web/public/brand/social-story-vertical-source.png`
- Story derived:
  - `web/public/brand/social-story-vertical.png` - 1080x1920 story/reel cover creative
- Prompt summary: launch campaign scenes showing the apple-to-baseball disguise, premium appraisal tools, and AI scan motifs, no image text.

## Usage

- Web metadata references `/brand/og-image.png`.
- PWA manifest references `/brand/app-icon-192.png` and `/brand/app-icon-512.png`.
- Browser and iOS icons reference `/brand/favicon-32.png` and `/brand/apple-touch-icon.png`.
- Social posts can use `/brand/social-feed-square.png` and `/brand/social-story-vertical.png` with platform-native copy overlays.

## Constraints

- Do not add text directly inside generated imagery.
- Use HTML, CSS, or share-card rendering for exact campaign copy.
- Keep the appraiser persona playful and confident, never insulting the player.
