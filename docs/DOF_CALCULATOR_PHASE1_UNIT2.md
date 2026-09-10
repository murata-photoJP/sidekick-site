# Sidekick DOF Calculator Phase 1 / Unit 2

- Route: `/tools/dof`; `build/site/build_site.py` generates `tools/dof.html` from a Jinja2 template.
- Architecture: Unit 1 calculation core → UI controller → presentation formatter / native SVG chart.
- Default: 35mm full frame, 50 mm, F4, 3.0 m, Traditional 30 µm (VF-02).
- Criterion: selected geometric blur threshold, not a universal human-vision boundary. Sensor and criterion remain independent.
- Curve: adaptive finite window, 161 caller-selected samples, analytic near/far crossings from the core, accessible text and SVG description.
- URL schema v1: `v`, `sensor`, `f`, `n`, `s`, `criterion`; custom states add `sw`, `sh`, or `c`. Invalid supplied state is detected and the UI reports use of safe defaults.
- Accessibility: semantic labels/results, keyboard-native controls and disclosures, visible focus, polite result summary, chart text alternative.
- Review fix: custom sensor errors appear beside its width/height fields; blank numeric values remain invalid. URL parse warnings use a persistent status element separate from form validation errors.
- Visual review: VF-02 and far-infinity curves retained a readable focus neighborhood, so the adaptive range was unchanged. Desktop 1280 px and mobile 375/320 px had no horizontal overflow; axis labels now state metres and micrometres.
- Deferred: Pixel Reference, 100% Monitor, Print, diffraction/MTF/EE, real-lens and macro UI, English page, and share UI.
