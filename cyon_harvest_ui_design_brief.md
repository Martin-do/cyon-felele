# CYON Harvest 2026 — UI/UX Design Brief & Build Instructions
### "Harvest of Divine Fulfillment" — Christ the Good Shepherd Catholic Church, Akobo/Felele, Ibadan

This document is a hand-off brief for the build agent. It extracts the visual identity
already established in the church's printed flyers and banners, translates it into a
design system, and specifies how each page/module of the harvest portal should look
and feel. The goal: the web portal should feel like a **natural digital extension of
the printed materials** — Father and the committee should recognize it instantly.

---

## 1. Brand Identity Reference

**Campaign name:** Harvest of Divine Fulfillment 2026
**Tagline (CYON):** "Let Your Light Shine"
**Scripture anchor:** Psalm 126:5 — "Those who sow in tears will reap with songs of joy."
**Target:** ₦5,000,000

**Source assets** (already uploaded — copy into `static/images/brand/`):
- `cyon_harvest_flyer.png` — full A4 portrait flyer (primary reference)
- `cyon-logo-transparent.png` — official CYON shield logo, transparent background
  (use as the canonical CYON logo everywhere; do not crop the logo from the flyer)
- `cyon_harvest_flyer_square.png` — square/social variant
- `IMG-20260611-WA0003.jpg` / `WA0004.jpg` — physical roll-up banners (clean basket
  graphic + activity schedule table — useful as a cropped hero asset)
- `IMG-20260611-WA0005.jpg` — church building exterior (use as hero background)

---

## 2. Design Tokens

### 2.1 Color Palette

```css
:root {
  /* Primary — deep forest green (headers, primary buttons, footer) */
  --harvest-green-900: #14301F;
  --harvest-green-800: #1B4332;
  --harvest-green-700: #245C3F;

  /* Gold / mustard (the "HARVEST" gradient, accents, badges) */
  --harvest-gold-500: #C9A227;
  --harvest-gold-400: #E0C158;
  --harvest-gold-gradient: linear-gradient(135deg, #E8C547 0%, #B8860B 100%);

  /* Cream / off-white background — matches flyer paper tone */
  --harvest-cream: #FAF6EC;
  --harvest-cream-card: #F4EFE2;

  /* Supporting */
  --harvest-brown: #8B5A2B;     /* roof/cross tone, used sparingly */
  --harvest-white: #FFFFFF;
  --harvest-text-dark: #1B3B2B; /* body text on cream */

  /* Status (for dashboard / live board) */
  --harvest-success: #2E7D4F;   /* fulfilled / paid */
  --harvest-pending: #C9A227;   /* pledged */
  --harvest-danger: #B3261E;    /* voided */
}
```

### 2.2 Typography

| Role | Style | Suggested fonts |
|---|---|---|
| Display headline ("HARVEST", "₦5,000,000") | Heavy/black weight, condensed-ish, uppercase | `Poppins ExtraBold` / `Montserrat Black` / `Archivo Black` |
| Script accent ("Join us to", "Let your light shine") | Flowing cursive, used **sparingly** as a small lead-in line | `Great Vibes` / `Pacifico` / `Allura` (Google Fonts) |
| Body & UI text | Clean, highly legible sans-serif | `Inter` / `Lato` / `Open Sans` |
| Numbers (counters, amounts) | Tabular figures, medium-bold | Same as body, `font-variant-numeric: tabular-nums` |

Load via Google Fonts:
```html
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;800&family=Great+Vibes&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

### 2.3 Iconography & Imagery Style
- Round, filled icon badges (gold or green circle backgrounds with white icons) —
  matches the "YOUR SUPPORT HELPS US" panel. Use a simple icon set (Lucide or Tabler)
  rendered inside `border-radius: 50%` colored circles.
- A wheat/grain stalk illustration (gold) appears as a recurring motif — use as a
  subtle corner decoration or section divider, never as a busy background.
- The harvest basket photo (vegetables/fruit) is the hero "warmth" image — usable on
  the landing page and receipt pages.
- Church building photo (`WA0005.jpg`) works well as a **hero background** with a
  dark green gradient overlay (`linear-gradient(to bottom, rgba(20,48,31,0.75), rgba(20,48,31,0.92))`)
  so white/gold text remains readable on top.

---

## 3. Landing Page Structure (`/` — public-facing)

This is the page people land on after scanning the QR code or clicking the shared link.
It should feel like the flyer, but interactive.

### Section 1 — Hero
- Background: church building photo with dark green gradient overlay
- Top bar: Archdiocese logo (left) + CYON shield logo (right), both on transparent
  background, small (~48px height)
- Script line: *"Join us to"* (Great Vibes, gold, ~28px)
- Headline: **"REACH OUR HARVEST TARGET"** — three lines, mixed white/gold per the
  flyer (e.g., "REACH OUR" white, "HARVEST" gold gradient, "TARGET" white)
- Below headline: a **live progress widget** (this is the key upgrade over the static
  flyer):
  - Large counter: `₦X,XXX,XXX` (animates count-up on page load)
  - Progress bar toward ₦5,000,000, gold fill on dark green track
  - Small text: "X contributors so far"
- CTA buttons (side by side): **"Donate / Pledge Now"** (gold filled) and
  **"View Live Board"** (outlined white)

### Section 2 — "Your Support Helps Us"
- Cream background card, dark green border
- 2x2 or 1x4 grid of icon + text pairs (reuse exact copy from flyer):
  - Organize a successful Harvest Celebration
  - Support youth evangelization activities
  - Fund parish youth projects
  - Strengthen community outreach and service
- Closing italic line: *"Together, we build a vibrant faith community."*

### Section 3 — "Be Part of the Success Story"
- Photo strip (3 images side by side, rounded corners, slight shadow) — placeholder
  for CYON activity photos. On mobile, switch to a horizontal scroll/carousel.
- Gold banner overlay text: "BE PART OF THE SUCCESS STORY"

### Section 4 — Donate / Contribute Panel
- Two-column layout (stacks on mobile):
  - **Left:** Bank transfer details card (dark green, gold header "DONATE NOW")
    - Bank: Union Bank
    - Account Name: Christ the Good Shepherd Catholic Church
    - Account Number: 0000313701 (large, monospace, with a "Copy" button)
  - **Right:** "Log Your Contribution" — this is where the actual web form replaces
    the static QR code. Short form: Name, Phone, Amount, Method (Cash/Transfer/POS),
    optional pledge toggle. Submit → redirect to receipt page.
- Below both: small text "Every donation counts!" (gold italic, matches flyer)

### Section 5 — Scripture & Closing
- Dark green full-width band
- Centered Psalm 126:5 quote in the script/italic style
- "No contribution is too small..." paragraph (cream text)

### Section 6 — Footer
- Dark green, gold text for campaign name
- Address: "Christ the Good Shepherd Catholic Church, Akobo, Ibadan"
- "HARVEST OF DIVINE FULFILLMENT 2026"
- Script tagline: "Let your light shine!"
- Links: Live Board · Member Login · Dashboard (staff only)

---

## 4. Module-Specific UI Instructions

### 4.1 Live Harvest Board (`/board/`) — projector display
- **Full dark-green background** (`--harvest-green-900`), high contrast for projection
- Top: small church + CYON logos, campaign name in gold
- Center: enormous ₦ counter (Poppins ExtraBold, 8–12rem on large screens), animates
  upward as new entries arrive via WebSocket
- Beneath counter: gold progress bar toward ₦5,000,000, with percentage label
- Right or bottom panel: live-scrolling feed of recent entries — each new entry
  slides in with a subtle fade/slide animation, shows Name + Amount + Method tag
- Method tags use small colored pills: Cash (gold), Transfer (green), POS (white/outline)
- Optional: wheat-stalk graphic in a corner as a quiet brand touch — must not
  distract from the counter

### 4.2 Recorder / Quick Logger (`/log/`) — mobile, used by recorders during Mass
- **Cream background**, minimal chrome — recorders need speed, not decoration
- Single column, large touch targets (min 48px height)
- Fields top to bottom: Name (with autocomplete dropdown per the implementation
  plan), Amount (large numeric keypad-friendly input), Method (3 large segmented
  buttons: Cash / Transfer / POS — green when selected)
- Submit button: full-width, gold, "Log Contribution"
- On success: brief full-screen green flash + checkmark animation, then auto-reset
  after ~1.5s — no need to tap anything to log the next person
- Small header shows recorder's station ID (A/B/C) so they always know which
  device they're on

### 4.3 Guest Contribution Form + Receipt (`/contribute/` → `/receipt/<ref>/`)
- Form page: same cream/green palette as landing page, friendly and warm —
  include the harvest basket image as a small decorative element
- Receipt page should feel like a **certificate of appreciation**, not a bare
  confirmation:
  - Gold border frame
  - Church + CYON logos at top
  - "Thank you, [Name]!" in script font
  - Reference number, amount, date, method displayed clearly
  - Psalm 126:5 quote at the bottom
  - "Print Receipt" button (CSS `@media print` styles to hide nav/buttons)

### 4.4 Member Hub (`/members/`)
- Same cream/green system, slightly more "dashboard-like" than the guest form
- PIN login screen: centered card on cream background, CYON logo above the form
- Member dashboard: personal progress ring or bar (levy paid vs. owed), pledge
  status card, simple "Log a Payment" button reusing the contribution form component

### 4.5 Staff Dashboard (`/dashboard/`)
- Lighter, more utilitarian — white background with green/gold accents only on
  headers, buttons, and the metric cards (per the Phase 5 implementation plan)
- Metric cards use the same icon-in-circle style as the "Your Support Helps Us"
  section for visual consistency, but smaller
- Data table uses alternating row shading in very light green/cream, not gray

---

## 5. Build Prompt (paste to your agent)

```
Using the design brief in cyon_harvest_ui_design_brief.md, build/restyle the
following templates to match the CYON Harvest 2026 brand:

1. Create base.html with the shared design tokens (CSS variables from section 2.1),
   Google Fonts import (section 2.2), and a shared header/footer matching section
   3 (logos, footer copy, tagline).

2. Build the landing page (templates/contributions/landing.html) following the
   six sections in section 3, in order. Use the church logo and CYON shield logo
   from static/images/brand/. The hero background should use WA0005.jpg with the
   dark green gradient overlay specified.

3. Style the live board (templates/live/board.html) per section 4.1 — large
   counter, gold progress bar, live-scrolling entry feed with slide-in animation.

4. Style the recorder quick-logger (templates/contributions/donation_form.html)
   per section 4.2 — cream background, large touch targets, segmented method
   buttons, success flash animation.

5. Style the guest receipt page (templates/contributions/receipt.html) per
   section 4.3 — certificate-style layout with gold border, print stylesheet.

6. Apply the lighter dashboard variant (section 4.5) to
   templates/dashboard/master.html without changing any of the
   functional/filter logic already implemented.

Do not introduce new color values outside the palette in section 2.1. Keep all
animations subtle (CSS transitions under 500ms, no bouncing/flashy effects
except the brief success flash on the recorder form).
```

---

## 6. Asset Checklist Before Build

- [ ] Export Archdiocese of Ibadan logo as transparent PNG (crop from flyer)
- [x] CYON shield logo — use cyon-logo-transparent.png directly (already done)
- [ ] Crop/export the Archdiocese of Ibadan circular logo as a standalone
      transparent PNG (currently only exists embedded in the flyer)
- [ ] Export the wheat/grain illustration as a standalone transparent PNG
- [ ] Export harvest basket photo (cropped, for receipt page)
- [ ] Save WA0005.jpg as the hero background source
- [ ] Confirm bank details (Union Bank, 0000313701) are stored as a constant/config
      value, not hardcoded in templates, so they can be updated centrally
