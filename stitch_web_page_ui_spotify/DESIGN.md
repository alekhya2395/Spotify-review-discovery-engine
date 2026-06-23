---
name: Obsidian Pulse
colors:
  surface: '#121414'
  surface-dim: '#121414'
  surface-bright: '#38393a'
  surface-container-lowest: '#0d0e0f'
  surface-container-low: '#1a1c1c'
  surface-container: '#1e2020'
  surface-container-high: '#292a2a'
  surface-container-highest: '#343535'
  on-surface: '#e3e2e2'
  on-surface-variant: '#bccbb9'
  inverse-surface: '#e3e2e2'
  inverse-on-surface: '#2f3131'
  outline: '#869585'
  outline-variant: '#3d4a3d'
  surface-tint: '#53e076'
  primary: '#53e076'
  on-primary: '#003914'
  primary-container: '#1db954'
  on-primary-container: '#004118'
  inverse-primary: '#006e2d'
  secondary: '#c8c6c5'
  on-secondary: '#313030'
  secondary-container: '#4a4949'
  on-secondary-container: '#bab8b7'
  tertiary: '#c8c6c5'
  on-tertiary: '#303030'
  tertiary-container: '#a2a1a0'
  on-tertiary-container: '#383838'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#72fe8f'
  primary-fixed-dim: '#53e076'
  on-primary-fixed: '#002108'
  on-primary-fixed-variant: '#005320'
  secondary-fixed: '#e5e2e1'
  secondary-fixed-dim: '#c8c6c5'
  on-secondary-fixed: '#1c1b1b'
  on-secondary-fixed-variant: '#474646'
  tertiary-fixed: '#e4e2e1'
  tertiary-fixed-dim: '#c8c6c5'
  on-tertiary-fixed: '#1b1c1c'
  on-tertiary-fixed-variant: '#474746'
  background: '#121414'
  on-background: '#e3e2e2'
  surface-variant: '#343535'
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  headline-md-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 16px
  md: 24px
  lg: 32px
  xl: 48px
  container-padding: 24px
  gutter: 16px
---

## Brand & Style

This design system embodies a **Modern / Corporate Dark** aesthetic, optimized for high-density data visualization and analytical workflows. It leverages a deep charcoal foundation to minimize eye strain during extended use, punctuated by vibrant, high-energy accents that draw attention to critical insights.

The personality is authoritative yet approachable, utilizing "Spotify-inspired" aesthetics to create a sense of familiarity and premium quality. It targets professional analysts and product owners who require clarity in complex datasets without sacrificing visual sophistication. The UI evokes a sense of "command and control," where information is structured within clear, identifiable containers that prioritize legibility and rapid scanning.

## Colors

The palette is built on a "True Dark" philosophy. The base background is near-black to provide maximum contrast for the content. 

- **Primary:** The iconic green is used sparingly for active states, key branding, and "Positive" status indicators to maintain its impact.
- **Surface Hierarchy:** Backgrounds use a tiered charcoal system. The base level is `#0A0A0A`, while primary containers (cards) use `#121212`. 
- **Sentiment Tokens:** A dedicated semantic palette is used for data visualization and status tags. These are calibrated for high legibility against dark backgrounds, using saturated hues to ensure color-coding is immediate and unmistakable.
- **Typography Colors:** Primary text is pure white (`#FFFFFF`) or high-contrast off-white, while secondary labels and metadata use a muted silver-gray (`#B3B3B3`) to establish a clear information hierarchy.

## Typography

This design system utilizes a dual-font strategy. **Plus Jakarta Sans** provides a modern, slightly geometric feel for headlines and display metrics, lending the interface a friendly but professional character. **Inter** is used for all functional text, data tables, and body copy due to its exceptional legibility and neutral tone.

Data points (like large metric numbers) should utilize a tighter letter spacing and semi-bold weights to emphasize scale. Labels for charts and table headers should be distinctly smaller and occasionally use uppercase styling to differentiate them from interactive content.

## Layout & Spacing

The layout is governed by a **Card-Based Grid** system. Content is organized into distinct functional modules (cards) that sit on a fluid 12-column grid.

- **Desktop:** 12-column grid, 16px gutters, 24px outer margins. Cards can span 3, 4, 6, or 12 columns depending on the complexity of the visualization.
- **Tablet:** 8-column grid. Complex cards (like the main data table) should allow horizontal scrolling or reflow to vertical stacks.
- **Mobile:** 4-column grid. All cards stack vertically. Padding is reduced to 16px to maximize screen real estate.

Spacing follows a strict 4px base unit to ensure rhythmic consistency. High-level containers use `md` (24px) padding, while internal card elements use `sm` (16px) or `xs` (8px) to maintain density.

## Elevation & Depth

This design system avoids traditional shadows in favor of **Tonal Elevation** and **Thin Outlines**. Depth is communicated through color luminance rather than physical metaphors.

1.  **Base Layer:** The darkest surface (`#0A0A0A`), acting as the canvas.
2.  **Card Layer:** Surfaces raised "closer" to the user are rendered in `#121212`. 
3.  **Interactive Layer:** Elements like buttons or active inputs use `#282828` or primary green to signify interaction.
4.  **Borders:** Cards and input fields feature a subtle 1px solid border (`#282828`) to define boundaries without adding visual weight. 

Shadows are used only for temporary overlays (modals or dropdowns), using a large, soft blur (24px) with high transparency (40%) to separate the element from the dense UI below.

## Shapes

The shape language is defined by **pronounced, friendly rounding**. This softens the "industrial" feel of the dark theme and aligns with modern app design standards.

- **Standard Containers:** Use 0.5rem (8px) for cards and main UI modules.
- **Interactive Elements:** Buttons and tags use a higher radius (1rem or full pill-shape) to distinguish them from structural containers.
- **Data Visualizations:** Bar charts and progress indicators should use rounded caps to match the overall UI geometry.

## Components

- **Cards:** The primary container. Must have a background of `#121212`, 8px corner radius, and 24px internal padding. 
- **Buttons:** 
    - *Primary:* Solid Spotify Green with black text, pill-shaped.
    - *Secondary:* Ghost style with 1px gray border and white text.
- **Sentiment Tags:** Subtle outlines or light backgrounds using the sentiment color tokens. They should include an icon (e.g., face emojis or arrows) to aid in quick interpretation.
- **Data Tables:** Row-based layout with subtle dividers (`#1F1F1F`). Header text is muted (`#B3B3B3`) and smaller than row content.
- **Inputs & Selects:** Dark background (`#1F1F1F`), 8px radius, with a clear focus state using the primary green border.
- **Charts:** Use the primary green for the most important data series. For categorical data, use the sentiment palette (Green/Red/Gray/Yellow).