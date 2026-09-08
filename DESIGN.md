---
name: High-Performance Terminal
colors:
  surface: '#131316'
  surface-dim: '#131316'
  surface-bright: '#39393c'
  surface-container-lowest: '#0e0e11'
  surface-container-low: '#1b1b1f'
  surface-container: '#201f23'
  surface-container-high: '#2a292d'
  surface-container-highest: '#353438'
  on-surface: '#e5e1e6'
  on-surface-variant: '#d7c3b4'
  inverse-surface: '#e5e1e6'
  inverse-on-surface: '#303034'
  outline: '#9f8d80'
  outline-variant: '#524439'
  surface-tint: '#ffb876'
  primary: '#ffd9ba'
  on-primary: '#4b2800'
  primary-container: '#ffb46e'
  on-primary-container: '#794403'
  inverse-primary: '#895113'
  secondary: '#cfc5b7'
  on-secondary: '#353026'
  secondary-container: '#4e483d'
  on-secondary-container: '#c0b7a9'
  tertiary: '#aaeaff'
  on-tertiary: '#003642'
  tertiary-container: '#7ad0ea'
  on-tertiary-container: '#00596b'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdcc0'
  primary-fixed-dim: '#ffb876'
  on-primary-fixed: '#2d1600'
  on-primary-fixed-variant: '#6b3b00'
  secondary-fixed: '#ebe1d2'
  secondary-fixed-dim: '#cfc5b7'
  on-secondary-fixed: '#201b12'
  on-secondary-fixed-variant: '#4c463b'
  tertiary-fixed: '#b1ecff'
  tertiary-fixed-dim: '#7cd2ec'
  on-tertiary-fixed: '#001f27'
  on-tertiary-fixed-variant: '#004e5e'
  background: '#131316'
  on-background: '#e5e1e6'
  surface-variant: '#353438'
  surface-elevated: '#121217'
  border-subtle: '#1C1C22'
  terminal-green: '#A6E22E'
  terminal-blue: '#66D9EF'
typography:
  headline-xl:
    fontFamily: JetBrains Mono
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: JetBrains Mono
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: JetBrains Mono
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.2'
  body-md:
    fontFamily: JetBrains Mono
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  body-sm:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.5'
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: '1.0'
    letterSpacing: 0.05em
  code-block:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.7'
spacing:
  unit: 4px
  gutter: 24px
  margin-safe: 32px
  container-max: 1200px
---

## Brand & Style

The design system is built for performance, precision, and technical rigor. It targets a developer-centric audience that values low-latency tools and high information density. The aesthetic is "Modern Terminal Brutalism"—a fusion of classic command-line interfaces with contemporary high-contrast web design.

The style is characterized by:
- **High-Contrast Minimalist:** Deep, ink-black backgrounds paired with warm, legible text and sharp accent highlights.
- **Developer-Centric Utilitarianism:** Every element serves a functional purpose; decorative fluff is replaced by structural borders and monospaced precision.
- **Technical Sophistication:** The interface feels like a sophisticated piece of hardware, emphasizing stability and speed.

## Colors

The palette is anchored in a deep, near-black neutral (`#08080B`) to provide maximum contrast for technical text. 

- **Primary:** A warm, high-visibility amber (`#FFB46E`) used for primary actions, critical status indicators, and branding.
- **Secondary:** A soft, high-legibility parchment (`#E2D8C9`) used for primary body text and significant labels to reduce eye strain compared to pure white.
- **Accents:** Neon-inspired greens and blues are reserved for syntax highlighting, terminal outputs, and success/info states, maintaining the "IDE" aesthetic.
- **Surface Strategy:** Use slight tonal shifts for depth. Backgrounds remain flat, while containers use a slightly lighter grey (`#121217`) with sharp borders.

## Typography

The typography system relies exclusively on **JetBrains Mono**. This reinforces the terminal identity and ensures that alignment, indentation, and technical data are rendered with mathematical precision.

- **Headlines:** Use tight tracking and heavy weights. They should feel impactful and structural.
- **Body:** Generous line heights are used for long-form technical documentation to maintain readability against the dark background.
- **Labels:** Small caps or all-caps styling should be used for secondary navigation and metadata to distinguish them from executable content.

## Layout & Spacing

This design system utilizes a **Fixed Grid** approach for desktop to mirror the structured environment of a terminal window, while transitioning to a fluid layout for mobile.

- **Grid:** A 12-column grid with 24px gutters. Elements should snap to grid lines to maintain a "blocky," engineered feel.
- **Spacing Rhythm:** Based on a 4px baseline. Use 8px, 16px, 24px, 32px, 48px, and 64px increments for all padding and margins.
- **Density:** High information density is encouraged. Group related technical data closely, using structural borders rather than whitespace to define sections.

## Elevation & Depth

In keeping with the terminal aesthetic, this system avoids traditional shadows. Depth is conveyed through **Tonal Layers** and **Bold Borders**.

- **Layers:** Use `#121217` for cards or elevated sections. This subtle lift creates hierarchy without breaking the flat, technical feel.
- **Borders:** Use 1px solid borders (`#1C1C22`) for all containers. For active or focused states, the border should switch to the Primary Amber or Terminal Green.
- **Backdrop:** For modals or overlays, use a heavy background dim (80% opacity black) to maintain focus on the technical task at hand.

## Shapes

The shape language is strictly **Sharp (0px)**. 

Every UI element—buttons, input fields, cards, and tags—must have square corners. This reinforces the brutalist, "unrefined" hardware aesthetic. The only exception is for circular icon buttons if strictly necessary for platform conventions, though square enclosures are preferred.

## Components

- **Buttons:** Large, sharp rectangles. Primary buttons use a solid Amber background with black text. Secondary buttons use a 1px Secondary-colored border with no fill. Hover states should "invert" the colors or increase border thickness.
- **Input Fields:** Styled like a command line. A 1px border on the bottom or all sides, using a blinking block cursor `_` metaphor for focus states.
- **Chips/Tags:** Small, sharp-edged boxes with monochromatic fills or subtle borders. Used for categorizing languages (e.g., "Rust", "C++") or status.
- **Code Blocks:** Encapsulated in a slightly lighter background (`#121217`) with a specific syntax highlighting theme that utilizes the named terminal colors.
- **Lists:** Use monospaced bullet points (e.g., `> ` or `- `) instead of standard circular bullets to maintain the CLI persona.
- **Cards:** Minimalist containers defined by 1px borders. Titles should be separated from content by a 1px horizontal rule.