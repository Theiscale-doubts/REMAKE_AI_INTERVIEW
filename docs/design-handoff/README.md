# Handoff: VoxHire Premium Dark Redesign

## Overview
Visual redesign of the VoxHire AI Interview Platform (internal tool by The iScale). Candidates land here via a private link and complete a voice-based, proctored AI interview. This handoff restyles all four screens to a premium enterprise dark theme ("90% premium black / 10% deep crimson") **without changing any logic, routing, API calls, state management, or user flow**.

Target codebase: `frontend/src` — React + TypeScript + Tailwind (v4 syntax, tokens in `index.css`), pages in `src/pages/Home.tsx`, `Interview.tsx`, `Results.tsx`, shared header/`PoweredByIScale.tsx`.

## About the Design Files
The `.dc.html` files in this bundle are **design references created in HTML** — interactive prototypes showing intended look and behavior. They are NOT production code. The task is to **recreate these designs inside the existing React/Tailwind codebase**, reusing its components, state, and handlers exactly as they are. Only classNames / CSS tokens / markup structure inside existing components should change.

## Fidelity
**High-fidelity.** Colors, typography, spacing, radii, and shadows are final. Recreate pixel-perfectly. All values below are exact.

## Hard Constraints (from product owner)
- Do NOT modify business logic, routing, API calls, auth, state management, validation, or flow.
- Remove marketing/landing-page content: privacy/support links, promotional copy. Keep only candidate-relevant info.
- Red is reserved for: primary actions, active states, focus states, progress, important status. Never decorative everywhere.
- No glassmorphism, no neon/glow, no bouncing animations.

## Design Tokens

Colors (define as CSS variables / Tailwind theme tokens in `index.css`):
- `--bg` page background: `#050505`
- `--bg-2` secondary background: `#0B0B0C`
- `--surface` card: `#111214`
- `--surface-hi` elevated card: `#17181B`
- `--border`: `rgba(255,255,255,0.06)` (elevated cards use `0.08`)
- `--accent` primary: `#B11226`
- `--accent-hover`: `#C81D25`
- `--accent-pressed`: `#D92B32`
- `--accent-deep`: `#6E0F1E`
- `--text-hi`: `#F5F5F5`
- `--text-mid`: `#B3B3B8`
- `--text-mut`: `#7C7C84`
- Success (proctoring OK / positive): `#5FA47F` (badge text lighter: `#7FBF9B`)
- Warning / "areas for improvement": copper-bronze `#C99A72` (body text `#CBAE96`) — NOT yellow/amber
- Accent-tinted text on dark red chips: `#E05860`, `#DFA2A8`, `#C4818A`

Typography:
- Font: **Archivo** (Google Fonts, weights 400/500/600/700). Replaces Inter everywhere.
- H1: 52px (Home hero) / 38px (Setup), weight 650, letter-spacing -0.03em, line-height ~1.07
- Card titles: 17–20px, weight 600, letter-spacing -0.01/-0.02em
- Body: 13–16.5px, `--text-mid`, line-height 1.6–1.75
- Uppercase micro-labels: 9.5–11px, weight 500, letter-spacing 0.14–0.2em, `--text-mut`
- Numbers: `font-variant-numeric: tabular-nums`

Spacing / radii / shadows:
- Card radius: 14–16px; inner tiles/inputs/buttons: 10–12px; pills: 999px
- Card shadow: `inset 0 1px 0 rgba(255,255,255,0.04), 0 8px 30px rgba(0,0,0,.35)`
- Hero checklist card (Home): deeper `0 20px 50px rgba(0,0,0,.5), 0 0 80px #B112260A` with hover intensifying the crimson wash to `#B1122614`
- Card internal padding: 24–32px; page gutters 28–32px

Motion:
- 200–300ms, `ease-out` (entrances use `cubic-bezier(.16,1,.3,1)` 500–600ms fade-up from 12px)
- Hover: `translateY(-1px)` (primary CTA -2px) + slight brightness(1.08); pressed brightness(0.95)
- Staggered fade-up on checklist rows (+0.08s per row)

## Shared Elements (all screens)

### Header
- Sticky, height 64px, `rgba(5,5,5,.82)` + `backdrop-filter: blur(16px)`, bottom border `--border`.
- Left: text-only wordmark, two lines: "VOXHIRE" (15px, 700, letter-spacing 0.1em) over "AI INTERVIEW PLATFORM" (9.5px, 500, tracking 0.2em, uppercase, `--text-mut`). **No icon/logo mark** (the cyan wave icon is removed).
- Right: "POWERED BY" micro-label (9.5px, uppercase, tracking 0.18em, `--text-mut`) + iScale logo image at height 16px, whole group at opacity 0.65. **Logo renders directly on dark — no white chip/background behind it** (`iscale-logo.png` is red-on-transparent).

### Footer
- Top border `--border`, padding 18px 28px. Left "© 2026 VoxHire. All rights reserved." (13px `--text-mut`); right: same Powered-by treatment as header. **No privacy/support links.**

### Buttons
- Primary: `linear-gradient(180deg,#C81D25 0%,#B11226 100%)`, border `rgba(255,255,255,0.1)`, radius 12px, shadow `inset 0 1px 0 rgba(255,255,255,0.14), 0 8px 30px rgba(0,0,0,.35)`, weight 600, white-space nowrap. Hover: lift 1–2px + brightness 1.08.
- Secondary: `#17181B` bg, border `rgba(255,255,255,0.08)`, weight 500. Hover: border → `rgba(200,29,37,.5)`.
- Ghost/tertiary (Home "Interview Guidelines"): transparent bg, border `rgba(255,255,255,0.07)`, text `--text-mid`; hover border `rgba(255,255,255,0.16)`, text `--text-hi`.
- Disabled: opacity 0.4.

### Inputs / Select
- Bg `#0B0B0C`, border `rgba(255,255,255,0.08)`, radius 10px, padding 13px 16px (40px left when leading icon), 13.5px Archivo.
- Placeholder `#7C7C84`.
- Focus: border `#B11226` + ring `0 0 0 3px rgba(177,18,38,.15)`, no outline. Transition 200ms.

### Status pill
- Border `rgba(255,255,255,0.08)`, bg `#111214`, radius 999px, padding 7px 14–16px, 12px text `--text-mid`, with 6px crimson dot pulsing (opacity 1→0.35, 2s ease-in-out infinite).

## Screens

### 1. Home (`Home.tsx`) — ref `01 Home.dc.html`
Two-column grid (`1.05fr 1fr`, gap 56px, max-width 1200px, aligned to top, padding 24px 32px):
- **Left (hero)**: status pill "Welcome — your AI interview is ready"; H1 "Your AI Interview / Starts Here" (second line `--text-mid`); one paragraph; CTA row: primary "Start Interview" (mic + arrow icons) + ghost "Interview Guidelines". Below CTAs: decorative animated waveform strip (36 thin 3px bars, mostly `#232428`, every 5th bar crimson at 60% alpha, gentle scaleY oscillation 1.7–3.1s alternate) and a micro-label "VOICE-FIRST · PROCTORED · REVIEWED BY HUMANS". A very subtle blurred radial crimson wash (~7% alpha) drifts behind the hero (14s loop). Keep this restrained.
- **Right (Before You Begin card)**: surface card. Header block (title + "A quick checklist…"). Five checklist rows (36px icon tile `#17181B` + label + small success check `#5FA47F` at 70% opacity), rows fade-up staggered. Divider. 2×2 grid of info tiles (`#0B0B0C`, radius 12px): Estimated duration "10–15 minutes", Assessment scope "9–10 questions, adapts as you go", Interview mode "Voice AI", Evaluation "AI + recruiter review". Tile labels uppercase 10px; hover border brightens.
- Checklist icon strokes use `color-mix(in oklab, #B11226 65%, #B3B3B8)` (muted rosy accent).
- **Removed:** all landing-page marketing sections, privacy/support links, bottom duplicate CTA bar.

Tweakable design knobs prototyped (optional to port): accent color, surface tone, split vs centered layout.

### 2. Interview Setup (`Interview.tsx` setup state) — ref `02 Interview Setup.dc.html`
- Page header block: pill "Step 1 of 2 · Interview setup", H1 38px "Set up your interview", one supporting line. Compact vertical rhythm (32px main padding, 32px below intro).
- Grid `1fr 0.85fr`, gap 24px:
  - **Left card "Your details"**: header strip w/ bottom border; body 28px padding, 24px gaps. Fields: profile photo (76px rounded-14 preview tile + secondary "Upload photo" button), Full name*, Email*, Invite code, Job role (custom-styled select w/ chevron; helper text under). Required asterisk in `#C81D25`. Leading icons inside inputs at `--text-mut`. Footer strip (`rgba(5,5,5,.45)`, top border) with full-width primary "Start interview".
  - **Right column**: "What to expect" card with 2×2 info tiles (Questions "9–10 adaptive", Duration "≈ 15–20 min", AI interviewer "Speaks aloud", Your answers "Voice, transcribed") + two green-check caveat lines; "Preparation tips" card with 4 numbered rows (20px numbered chips, number in `#C81D25`); small privacy note strip (shield icon, 11.5px `--text-mut`).

### 3. Live Interview (`Interview.tsx` active state) — ref `03 Live Interview.dc.html`
- Header adds: elapsed-time pill (pulsing crimson dot + tabular mm:ss), candidate name/email right-aligned, "Exit" text button. Below header: 2px progress track `#17181B` with fill `linear-gradient(90deg,#6E0F1E,#B11226)`, width = qNum/total, 700ms ease-out.
- **Proctoring monitor**: fixed top-right (top 84px, right 16px, width 212px), card w/ header row ("PROCTORING" + green pulsing dot), black 150px video area, "Face detected" strip (green tint bg `rgba(95,164,127,.06)`, text `#5FA47F`), "Tab switches: 0" strip. Main column is right-padded so content never sits under it.
- **Question card** (elevated `#17181B`): chip "QUESTION N OF 9" (crimson-tinted: border `rgba(177,18,38,.4)`, bg `rgba(177,18,38,.08)`, text `#E05860`) + "Voice answer" hint; question 26px/1.35; replay-speaker icon button 44px top-right; "Interviewer is speaking…" line when TTS active.
- **Recording stage** (inside question card): graphite panel `#0B0B0C`, radius 14px; when recording, border `rgba(177,18,38,.28)` + faint radial crimson wash at top. Center-aligned waveform: 48 bars, 3.5px wide, idle `#1E1F23`, recording `rgba(200,29,37, .35–1)` scaled by level, height 6–94%, 120ms transitions. Status strip below (top border, `rgba(5,5,5,.35)` bg): status text left (recording state uses rosy `#DFA2A8` + pulsing dot w/ soft ring `0 0 0 3px rgba(177,18,38,.15)`); right, REC pill: crimson-tinted pill, "REC" 10.5px tracking 0.12em `#C4818A` + tabular timer `#DFA2A8`.
- **Controls row**: primary "Start recording" (switches to dark crimson-outline "Recording…" state while active — bg `rgba(177,18,38,.08)`, border `rgba(177,18,38,.4)`, text `#DFA2A8`); secondary "Stop"; secondary "Retake"; spacer; primary "Submit answer". Disabled = opacity 0.4.
- **Transcript card** (appears after transcription): "Your answer" w/ green headphones icon, word-count pill, scrollable transcript (max-height 176px, 14.5px/1.7 `--text-mid`).
- **Complete state**: centered card, 64px green-tinted check tile, "Interview complete", thank-you line, primary "View my results".

### 4. Results (`Results.tsx`) — ref `04 Results.dc.html`
- Header variant: "Back" link left, "INTERVIEW REPORT" centered, Powered-by right.
- Grid `1fr 2fr`, gap 24px:
  - **Left aside**: Candidate card (56px avatar tile, name/email, three info rows in `rgba(5,5,5,.5)` tiles: role, questions, date; Proctoring-flags tile with green check + 4 label/value rows in 11.5px). Overall-score card (elevated surface, centered): uppercase label, 72px tabular score, "out of 10", verdict pill (green-tinted "Excellent" w/ thumbs-up). Primary full-width "Download PDF report". **No "New interview" button.**
  - **Right column**: "Feedback" card (elevated, crimson-tinted icon tile, 3 paragraphs 14.5px/1.75). "Areas for improvement" card — **copper-bronze `#C99A72` treatment, not yellow**: icon tile + heading in copper, item rows `rgba(201,154,114,.05)` bg / `.14` border, text `#CBAE96`. "Performance breakdown" card: green trend icon; 3 labeled bars (7px track `#26272B`, fill `linear-gradient(90deg,#6E0F1E,#B11226)`, animate width from 0, staggered 0/.15/.3s).
- Score color logic in code (`getScoreColor`) should map: high → green `#5FA47F`, mid → copper `#C99A72`, low → crimson `#D92B32`.

## Interactions & Behavior
All existing handlers, timers, MediaRecorder logic, TTS, proctoring detection, tab-switch counting, API calls, and navigation stay untouched. The prototypes simulate recording/transcription purely for visual reference — ignore their JS logic.

## State Management
No changes. Reuse existing state exactly.

## Assets
- `assets/iscale-logo.png` — red-on-transparent iScale wordmark (already in codebase as `public/iscale-logo.png`). Render directly on dark, no white backing.
- Icons: lucide-react (already a dependency) — mic, arrow-right, volume-2, wifi, clock, list-ordered, shield-check, camera, user, mail, briefcase, headphones, send, square, rotate-ccw, download, trending-up, target, file-text, thumbs-up, check-circle-2.
- Font: Archivo via Google Fonts (`wght@400;500;600;700`).

## Files in this bundle
- `01 Home.dc.html` — Home / landing checklist screen
- `02 Interview Setup.dc.html` — candidate details + what to expect
- `03 Live Interview.dc.html` — live question, recording stage, proctoring monitor, complete state
- `04 Results.dc.html` — report: candidate, score, feedback, breakdown
- `support.js` — prototype runtime (ignore; reference only so the HTML files open in a browser)
- `assets/iscale-logo.png`

Open the `.dc.html` files in a browser to inspect exact rendering. Implement in React/Tailwind using the tokens above.
