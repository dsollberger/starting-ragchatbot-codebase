# Frontend Changes

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
