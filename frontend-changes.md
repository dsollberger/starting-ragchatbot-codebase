# Frontend Changes

## Dark/Light Theme Toggle

## Summary

Added a toggle button that lets users switch between the existing dark theme and a new light theme, with the choice persisted across sessions.

## Files Changed

### `frontend/index.html`
- Added a `#themeToggle` `<button>` as the first element inside `<body>` (before `.container`), so it sits above the layout regardless of the (currently hidden) header.
- The button contains two inline SVG icons (sun and moon) that cross-fade/rotate depending on the active theme.
- Includes `aria-label`, `aria-pressed`, and `title` attributes for accessibility; the icons are `aria-hidden`.

### `frontend/style.css`
- Added `:root[data-theme="light"]` block that overrides all existing CSS custom properties (`--background`, `--surface`, `--surface-hover`, `--text-primary`, `--text-secondary`, `--border-color`, `--assistant-message`, `--shadow`, `--focus-ring`, `--welcome-bg`) with light-mode equivalents while keeping `--primary-color`/`--primary-hover` consistent for brand continuity and contrast.
- Added `transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease` to `body` and the main themed surfaces (sidebar, chat area, messages, input, buttons, stat/suggested items) so switching themes animates smoothly instead of snapping.
- Added `.theme-toggle` styles: a fixed-position circular button in the top-right corner (`top: 1rem; right: 1rem`), styled with existing theme variables (`--surface`, `--border-color`, `--shadow`, `--focus-ring`) so it automatically matches both themes.
- Added `.theme-icon` cross-fade/rotate animation: the moon icon is visible by default (dark theme), and `[data-theme="light"]` swaps visibility to the sun icon.
- Added a small responsive rule shrinking the toggle button slightly on mobile widths (`max-width: 768px`).

### `frontend/script.js`
- Added `themeToggle` to the cached DOM elements and wired a `click` listener to it in `setupEventListeners()`.
- Added `initializeTheme()`, called on `DOMContentLoaded`, which reads a saved preference from `localStorage` (defaulting to `dark`) and applies it before the rest of the UI loads.
- Added `applyTheme(theme)`, which sets/removes the `data-theme="light"` attribute on `document.documentElement`, updates the toggle's `aria-pressed`/`aria-label` for screen readers, and persists the choice to `localStorage`.
- Added `toggleTheme()`, which flips between `dark` and `light` and calls `applyTheme()`.

## Behavior Notes

- Theme preference persists across page reloads via `localStorage` (`theme` key).
- The toggle is a native `<button>`, so it's keyboard-focusable and activates on both `Enter` and `Space` without extra JS.
- Verified in a headless browser: toggling switches `data-theme`, updates the icon and `aria-label`, and the choice survives a reload.

## Code quality tooling

Added Prettier (formatting) and ESLint (linting) for the `frontend/` directory (vanilla JS/HTML/CSS — no existing build step or Node tooling was present).

- **`package.json`** (new, repo root) — devDependencies `prettier` and `eslint`, plus scripts:
  - `npm run format` — formats `frontend/**/*.{js,css,html}` with Prettier
  - `npm run format:check` — checks formatting without writing (CI-friendly)
  - `npm run lint` — runs ESLint on `frontend/**/*.js`
  - `npm run lint:fix` — runs ESLint with autofix
  - `npm run quality` — runs `format:check` then `lint`
- **`.prettierrc.json`** (new) — 4-space indent, single quotes, semicolons, 100-char print width, matching the existing code style in `script.js`/`style.css`.
- **`.prettierignore`** (new) — excludes `node_modules/`, `backend/`, `docs/`, lockfiles.
- **`eslint.config.js`** (new, flat config) — scoped to `frontend/**/*.js`, declares browser globals used by the app (`window`, `document`, `fetch`, `console`, `Date`, and `marked` from the CDN script tag), with rules for unused vars, `no-undef`, `eqeqeq`, `no-var`/`prefer-const`.
- **`.gitignore`** — added `node_modules/`.

## Formatting pass

Ran `npm run format` once to normalize existing files to the new Prettier config: `frontend/index.html`, `frontend/script.js`, `frontend/style.css`. Changes are whitespace/quote-style/attribute-wrapping only — no behavior changes. `npm run lint` passes with no errors.

## Usage

```bash
npm install       # one-time setup
npm run quality   # format check + lint, e.g. before committing
npm run format    # auto-fix formatting
npm run lint:fix  # auto-fix lint issues
```
