# Changelog

- 2026-11-07 · redesign slice 8 (app 0.15.6): the setting `CVWRITE_HOME` exists, off by default and refused in production; on in dev, a visitor with no session cookie at `/` sees a placeholder page. Nothing changes for any real visitor.
- 2026-11-04 · redesign slice 7 (app 0.15.5): the three web fonts are served as woff2 files cut to the Latin letters, 145,572 bytes in place of 524,216; every page looks as before. The cut is remade by `fonts/build_web.py` (dev-only), and a test keeps every letter the app's text uses.
- 2026-11-03 · redesign slice 6 (no app change): the home's cut-paper art, 20 WebP images in `app/static/art/`, and the seeded generator that makes them in `gen/` (dev-only). No page shows them yet.
- 2026-11-03 · redesign slice 5 (no version change): `.webp` files are served as `image/webp` on any machine, ready for the home's art. Every other file type is unchanged.
- 2026-11-03 · redesign slice 4 (no app change): a test now lists the scripts in `app/static`, `fonts/` and the templates; a script that is not on the list, or is loaded on a page it is not listed for, fails the test suite. Only `upload.js` on the profile page is listed.
- 2026-10-30 · redesign slice 3 (app 0.15.4): dark mode. On a device set to dark, every page opens in the dark theme; it follows the device only, with no switch. Text on coral and marigold stays navy, the QR frame stays white so it scans, and the focus ring is coral on dark surfaces.
- 2026-10-29 · redesign slice 2 (app 0.15.3): the light look matches the target where it reads well. The brand mark is coral; muted text is `#6A7586` on white slabs and stays `#566275` on the ground and quiet slabs; the focus ring is coral on white slabs and ink elsewhere and on coral buttons.
- 2026-10-28 · redesign slice 1: every page opens in the new look (light theme). `betterjobs.css` and three new fonts replace `calm.css`; the shell in `base.html` is rebuilt.
