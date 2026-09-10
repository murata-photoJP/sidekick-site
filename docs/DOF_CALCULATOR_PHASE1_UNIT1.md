# Sidekick DOF Calculator Phase 1 / Unit 1

## Routing decision

`/tools/dof` is **ACCEPTED** as the first Japanese route.

- The site is statically deployed by Vercel with `cleanUrls: true` and `trailingSlash: false`.
- A future `tools/dof.html` therefore maps to `/tools/dof` without a custom rewrite.
- No existing `tools/dof.html`, `/tools/dof` redirect, rewrite, page registration, or generated output exists.
- The existing `tools/` files are repository-operation Python scripts with distinct filenames. They are not a dynamic router.
- Unit 1 creates no page or route scaffold. Page generation and navigation integration remain a later UI unit.

Before the UI unit creates `tools/dof.html`, repeat the collision check because the repository may have advanced.

## Existing site architecture

- Runtime: static HTML/CSS/browser JavaScript; Python is used only for builds and repository tools.
- Templates/build: Jinja2 with separate `site`, `knowledge`, `development-log`, and `story` builders.
- Package manager: npm metadata exists for server-side Firebase dependencies; no frontend bundler is configured.
- Tests: pytest is the established build/regression framework. Unit 1 uses Node's dependency-free built-in test runner for the browser-native ES module.
- Styling: page and shared static CSS; no component framework or CSS preprocessor.
- Localization: paired Japanese and `/en/` templates registered explicitly; no runtime i18n library.
- Deployment: repository-root static deployment to Vercel; clean URLs remove `.html` from public paths.
- Charts: no shared chart dependency is available. Unit 1 does not add one.
- Accessibility: shared Jinja headers and page templates contain semantic/ARIA patterns; the calculation core contains no presentation layer.

## Unit 1 core boundary

Production module: `assets/js/dof/calculation-core.mjs`.

- Canonical length unit: millimetres.
- Model: ideal paraxial thin lens, explicitly tagged `MODEL`.
- Sensor presets and criterion presets are separate objects.
- Traditional 0.030 mm is a mutable UI reference value represented as `REFERENCE`, not a format-derived physical constant.
- Infinity is represented by `farMm: null` plus `farIsInfinite: true`.
- Continuous samples are caller-parameterized; no unexplained fixed sample count is embedded in the core.
- Close-focus magnification is an ideal-model estimate. Real-lens magnification and principal-plane state remain `UNKNOWN`.
- No display rounding, translated UI strings, page markup, chart code, URL parser, or Phase 2 viewing geometry is included.

## Test commands

```powershell
node --test tests/tools/test_dof_calculation_core.mjs
python -m pytest
python build/site/build_site.py --output build-output/site --validate-only
```

The exact executable paths depend on the local environment. Codex desktop may use its bundled Node.js and Python runtimes.
