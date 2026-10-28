"""CHECK 3 of redesign S-001: the shell and the old pages at every width, measured in headless Chrome on the real pages
(stand-in data). Covers AC-19, AC-22 to AC-45, AC-64, AC-68 to AC-71 and the font-failure part of AC-14. Fails before
the work: the header, balance, banners and footer do not lay out as AC-22 to AC-42 say, and there is no new stylesheet.
senior-lead-Sonnet5.5-agent, 2026-10-28"""
import re
import unittest

import redesign_s001_common as C
from support import CVCase

INK, SLAB, GROUND, MARIGOLD, MUTED = "rgb(19, 35, 58)", "rgb(255, 255, 255)", "rgb(242, 241, 237)", "rgb(243, 180, 60)", "rgb(86, 98, 117)"
ERRORS = ("rgb(180, 35, 24)", "rgb(255, 90, 71)", "rgb(194, 56, 42)")
HDR = [320, 390, 479, 480, 600, 839, 840, 1024, 1280]
ALL = sorted(set([320, 360, 390, 768, 1024, 1280, 1440] + list(range(320, 1441, 40)) + HDR))
LONG_TITLE = "Senior Customer Success and Onboarding Specialist, Southeast Asia Region (Hybrid, Sample City)"
SECTION = {"profile": "/profile", "generate_notready": "/generate", "credits": "/credits", "account": "/account",
           "applications": "/applications", "admin": "/admin"}

LIB = r"""
const q = s => doc.querySelector(s), qa = s => [...doc.querySelectorAll(s)];
const cs = (e, p) => win.getComputedStyle(e, p || null);
const KEYS = ['font-size','font-weight','font-family','color','background-color','border-top-color','border-top-width','border-top-left-radius','text-decoration-line',
  'opacity','order','position','text-overflow','pointer-events','display','overflow-x','overflow-y','margin-left','outline-style','outline-width','outline-offset','outline-color','box-shadow','clip-path','transform','background-image'];
const R = (e, deep) => { if (!e) return null; const r = e.getBoundingClientRect(), c = cs(e), o = {x: r.x, y: r.y + win.scrollY, w: r.width, h: r.height, r: r.right, b: r.bottom + win.scrollY,
  t: (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60), sw: e.scrollWidth, cw: e.clientWidth, sh: e.scrollHeight, ch: e.clientHeight, href: e.getAttribute('href'), cur: e.getAttribute('aria-current'),
  dis: e.disabled || e.getAttribute('aria-disabled') || null};
  for (const k of KEYS) o[k] = c.getPropertyValue(k); return o; };
const vis = e => { const r = e.getBoundingClientRect(), c = cs(e); return r.width > 1.5 && r.height > 1.5 && c.visibility !== 'hidden' && c.display !== 'none'; };
const lineRects = e => { const out = []; const w = doc.createTreeWalker(e, NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) { if (!n.textContent.trim()) continue;
  const g = doc.createRange(); g.selectNodeContents(n); for (const r of g.getClientRects()) if (r.width > 0) out.push({x: r.x, y: r.y + win.scrollY, r: r.right, b: r.bottom + win.scrollY}); } return out; };
const header = q('header'), brand = q('header a[href="/"]'), nav = q('header nav, nav'), main = q('main'), footer = q('footer');
const bal = qa('header a[href="/credits"]').find(a => !a.closest('nav')) || null;
const navLinks = qa('nav a'), footLinks = qa('footer a, footer button');
const bannerEls = qa('.banner');
const skip = q('a.skip') || q('a[href="#main"]');
const out = {W};
out.overflow = doc.documentElement.scrollWidth > doc.documentElement.clientWidth;
out.docSW = doc.documentElement.scrollWidth; out.docCW = doc.documentElement.clientWidth;
out.clipped = qa('body *').filter(e => vis(e) && e.closest('table') == null && ['hidden','clip'].includes(cs(e).overflowX) && e.scrollWidth > e.clientWidth + 1 && (e.textContent || '').trim()).map(e => e.tagName + '.' + e.className).slice(0, 6);
out.ellipsis = qa('header *, footer *, .banner, .banner *, main h1, main h2, main p, main a, main label span').filter(e => cs(e).textOverflow === 'ellipsis').map(e => e.tagName + '.' + e.className).slice(0, 4);
const tap = qa('a, button, input:not([type=hidden]), select, textarea, summary').filter(e => vis(e) && e !== skip && !e.disabled);
out.overlaps = []; for (let i = 0; i < tap.length; i++) for (let j = i + 1; j < tap.length; j++) { const a = tap[i], b = tap[j]; if (a.contains(b) || b.contains(a)) continue;
  const A = a.getBoundingClientRect(), B = b.getBoundingClientRect(); const ox = Math.min(A.right, B.right) - Math.max(A.left, B.left), oy = Math.min(A.bottom, B.bottom) - Math.max(A.top, B.top);
  if (ox > 2 && oy > 2) out.overlaps.push([(a.textContent || a.name || a.tagName).trim().slice(0, 20), (b.textContent || b.name || b.tagName).trim().slice(0, 20)]); }
out.overlaps = out.overlaps.slice(0, 4);
out.hasHeader = !!header; out.header = R(header); out.brand = R(brand); out.bal = R(bal); out.nav = R(nav);
out.navLinks = navLinks.map(a => { const o = R(a); const f = a.firstElementChild; o.circle = f ? R(f) : null; o.label = R(a.querySelector('span:last-child') || a); o.hasDone = a.textContent.includes('(done)'); return o; });
out.balLines = bal ? lineRects(bal).map(r => Math.round(r.y)).filter((v, i, a) => a.indexOf(v) === i).length : 0;
out.balKids = bal ? [...bal.querySelectorAll('*')].map(e => ({t: e.textContent.trim().slice(0, 30), fs: cs(e).fontSize, color: cs(e).color, vis: vis(e), r: R(e)})) : [];
out.brandMarks = brand ? [brand, ...brand.querySelectorAll('*')].flatMap(e => ['', '::before', '::after'].map(p => { const c = cs(e, p || null); return {clip: c.clipPath, w: c.width, h: c.height, bg: c.backgroundColor, tf: c.transform, fw: c.fontWeight, fs: c.fontSize}; })) : [];
out.brandLabel = brand ? brand.getAttribute('aria-label') : null;
out.headerButtons = qa('header button, header [aria-expanded], header details, header input').length;
out.navDom = [brand, bal, ...navLinks].filter(Boolean).map(e => R(e));
out.bodySignedOut = doc.body.classList.contains('signed-out');
out.main = R(main); out.footer = R(footer); out.skipBefore = R(skip);
out.banners = bannerEls.map(e => { const o = R(e); o.buttons = e.querySelectorAll('button').length; o.an = cs(e).animationName; const a = e.querySelector('a'); o.link = a ? R(a) : null;
  const lr = lineRects(e); o.textRight = lr.length ? Math.max(...lr.filter(r => !a || r.x < a.getBoundingClientRect().x - 1).map(r => r.r), 0) : 0; o.bold = e.querySelector('b') ? R(e.querySelector('b')) : null; return o; });
out.footLinks = footLinks.map(e => { const o = R(e); o.tag = e.tagName; o.type = e.type || null; o.inForm = !!e.closest('form'); return o; });
out.footEls = footer ? [...footer.children].map(e => ({tag: e.tagName, t: e.textContent.trim().slice(0, 30), w: e.getBoundingClientRect().width})) : [];
out.docH = doc.documentElement.scrollHeight; out.version = footer && footer.lastElementChild ? R(footer.lastElementChild) : null;
out.fixed = qa('header, header *, nav, nav *, footer, footer *, .banner, .banner *').filter(e => ['fixed', 'sticky'].includes(cs(e).position)).map(e => e.tagName + '.' + e.className).slice(0, 4);
out.menuHints = qa('input[type=search], [role=search]').length; out.backLinks = qa('header a, footer a').filter(a => /^back$/i.test(a.textContent.trim())).length;
out.groups = {brand: brand ? [R(brand)] : [], bal: bal ? [R(bal)] : [], nav: navLinks.map(R), banner: qa('.banner a').map(R), foot: footLinks.map(R), btn: qa('.btn, button.pack').filter(vis).map(R),
  check: qa('label.check').filter(vis).map(R), sum: qa('summary').filter(vis).map(R), pack: qa('.pack').filter(vis).map(R), drop: qa('.drop').filter(vis).map(R), lang: qa('.lang-switch a').filter(vis).map(R)};
out.column = header ? R(header.parentElement) : null; out.colBg = header ? cs(header.parentElement).backgroundColor : null;
out.tables = qa('table').map(t => { let sc = null; for (let n = t; n && n !== doc.body; n = n.parentElement) if (['auto', 'scroll'].includes(cs(n).overflowX)) { sc = n; break; }
  const slab = t.closest('.card') || t.parentElement; return {tr: t.getBoundingClientRect().right, slabR: slab.getBoundingClientRect().right, scroller: !!sc, sw: t.scrollWidth}; });
out.imgs = qa('img').map(i => ({r: R(i), alt: i.alt, complete: i.complete, nat: i.naturalWidth, next: i.parentElement && i.nextElementSibling ? i.nextElementSibling.getBoundingClientRect().top + win.scrollY : null, slabR: (i.closest('.card, .qr') || i.parentElement).getBoundingClientRect().right}));
// keyboard: the skip link first, then focus rings on real controls
const first = qa('a, button, input, select, textarea, summary, [tabindex="0"]').filter(e => !e.disabled)[0];
out.firstFocusable = first ? {t: first.textContent.trim().slice(0, 30), href: first.getAttribute('href'), same: first === skip} : null;
if (skip) { skip.focus(); out.skipAfter = R(skip); out.skipFocused = doc.activeElement === skip; }
if (main) { main.focus(); out.mainRing = {style: cs(main).outlineStyle, width: cs(main).outlineWidth}; }
out.rings = {}; for (const [k, e] of Object.entries({brand, nav: navLinks[0], foot: footLinks[0], field: q('main input[type=text], main input[type=email], main textarea'), btn: q('main .btn'), sum: q('main summary'), box: q('main .check input')})) {
  if (!e) continue; e.focus(); const c = cs(e); out.rings[k] = {style: c.outlineStyle, width: c.outlineWidth, offset: c.outlineOffset, color: c.outlineColor}; }
out.scroll = {sh: doc.documentElement.scrollHeight, ch: doc.documentElement.clientHeight}; win.scrollTo(0, 400); out.headerAfterScroll = header ? header.getBoundingClientRect().top : null;
return out;
"""

INJECT_BAR = r"""
for (const b of doc.querySelectorAll('.banner b')) b.textContent = %s;
"""
INJECT_ALL = r"""
const bar = [...doc.querySelectorAll('.banner')].find(e => /CV/.test(e.textContent));
const t = %(title)s; if (bar && bar.querySelector('b')) bar.querySelector('b').textContent = t;
const dz = doc.querySelector('.drop-t'); if (dz) { dz.textContent = 'a-file-name-without-any-spaces-that-is-eighty-characters-long-for-the-drop-zone.docx'; dz.closest('.drop').classList.add('is-picked'); }
const sec = doc.querySelector('main section, main'); if (sec) { const p = doc.createElement('p'); p.textContent = 'We sent a 6-digit code to ' + 'a'.repeat(240) + '@example.com'; sec.appendChild(p); }
"""


class Shell(CVCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass() if hasattr(super(), "setUpClass") else None
        C.require_chrome()

    def setUp(self):
        super().setUp()
        if not hasattr(Shell, "R"):
            self.measure_all()

    def measure_all(self):
        pages = C.app_pages(self)
        Shell.who = {k: v[1] for k, v in pages.items()}
        with C.Site(pages) as site:
            paths = {k: f"/p/{k}.html" for k in pages}
            res = C.measure(site, list(paths.values()), ALL, LIB, height=900)
            Shell.R = {k: res[v] for k, v in paths.items()}
            short = C.measure(site, [paths[k] for k in ("profile", "generate_notready", "signin") if k in paths], [320], LIB, height=568)
            Shell.short = {k: short[paths[k]][320] for k in ("profile", "generate_notready", "signin") if k in paths}
            land = C.measure(site, [paths[k] for k in ("profile", "signin") if k in paths], [667], LIB, height=375)
            Shell.land = {k: land[paths[k]][667] for k in ("profile", "signin") if k in paths}
            inj = {}
            for k in ("profile_paused", "profile_heavy", "profile", "signin", "order", "admin", "owner_profile"):
                if k in paths:
                    js = INJECT_ALL % {"title": repr(LONG_TITLE)} + LIB
                    inj[k] = C.measure(site, paths[k], [320, 390, 1280], js, height=900)[paths[k]]
            Shell.inj = inj
            inj2 = {}
            js2 = INJECT_ALL % {"title": repr("X" * 60)} + LIB
            for k in ("profile_paused",):
                inj2[k] = C.measure(site, paths[k], [320, 390], js2, height=900)[paths[k]]
            Shell.inj2 = inj2
        with C.Site(pages, block_fonts=True) as site:
            res = C.measure(site, list(paths.values()), [320, 390], LIB, height=900)
            Shell.nofonts = {k: res[v] for k, v in paths.items()}

    # ---------------------------------------------------------------------------------------------- helpers
    def users(self):
        return [k for k, w in Shell.who.items() if w in ("user", "owner") and Shell.R[k][320]["bal"] and len(Shell.R[k][320]["navLinks"]) >= 5]

    def look(self):
        self.assertTrue(C.SHEET.exists(), "app/static/betterjobs.css does not exist yet")

    def collect(self, ac, bad):
        self.assertEqual(bad[:12], [], f"{ac}: {len(bad)} problems")

    # ---------------------------------------------------------------------------------------------- the six checks
    def test_ac68_no_page_scrolls_sideways_or_clips_or_overlaps(self):
        self.look()
        bad = []
        for name, by_w in Shell.R.items():
            for w, r in by_w.items():
                if r["overflow"]:
                    bad.append(f"{name}@{w}: scrolls sideways ({r['docSW']} > {r['docCW']})")
                if r["clipped"] or r["ellipsis"]:
                    bad.append(f"{name}@{w}: clipped {r['clipped']} {r['ellipsis']}")
                if r["overlaps"] and w in (320, 390, 768, 1280):
                    bad.append(f"{name}@{w}: overlap {r['overlaps']}")
        self.collect("AC-68", bad)

    def test_ac14_the_pages_hold_without_their_fonts(self):
        self.look()
        bad = [f"{n}@{w}" for n, by_w in Shell.nofonts.items() for w, r in by_w.items() if r["overflow"] or r["clipped"] or r["overlaps"]]
        self.collect("AC-14", bad)

    def test_ac69_real_content_does_not_overlap_clip_or_scroll_sideways(self):
        self.look()
        bad = []
        for runs in (Shell.inj, Shell.inj2):
            for name, by_w in runs.items():
                for w, r in by_w.items():
                    if r["overflow"] or r["clipped"] or r["overlaps"]:
                        bad.append(f"{name}@{w}: {r['overflow']} {r['clipped']} {r['overlaps']}")
        heavy = Shell.R["profile_heavy"]
        for w in (320, 390, 1280):
            t = heavy[w]["bal"]["t"]
            if not re.search(r"120\s*credits.*3 in use.*earliest expire 28 Sep 2027", t):
                bad.append(f"profile_heavy@{w}: balance reads {t!r}")
        owner = Shell.R["owner_profile"]
        for w in (320, 390, 1280):
            labels = [l["t"].replace("(done)", "").strip() for l in owner[w]["navLinks"]]
            for want in ("Profile", "Generate", "Applications", "Credits", "Account", "Admin"):
                if not any(want in l for l in labels):
                    bad.append(f"owner_profile@{w}: nav lacks {want}")
        for k in ("order",):
            for w in (320, 390, 1280):
                imgs = [i for i in Shell.R[k][w]["imgs"] if i["r"]["w"] and "QR" in i["alt"]]
                for i in imgs:
                    if i["nat"] != 0 or not i["alt"] or i["r"]["h"] < 10 or i["r"]["r"] > i["slabR"] + 1:
                        bad.append(f"order@{w}: blocked QR {i['r']['w']}x{i['r']['h']} right {i['r']['r']} slab {i['slabR']}")
                    if i["next"] is not None and i["next"] < i["r"]["b"] - 1:
                        bad.append(f"order@{w}: text below the QR moved up into it")
        self.collect("AC-69", bad)

    def test_ac70_nothing_sticks_and_a_short_screen_scrolls(self):
        self.look()
        bad = []
        for name, by_w in Shell.R.items():
            for w, r in by_w.items():
                if r["fixed"]:
                    bad.append(f"{name}@{w}: fixed or sticky {r['fixed']}")
        for label, group in (("320x568", Shell.short), ("667x375", Shell.land)):
            for name, r in group.items():
                if r["header"] and r["scroll"]["sh"] > r["scroll"]["ch"] and r["headerAfterScroll"] is not None and r["headerAfterScroll"] > -r["header"]["h"] + 1 and r["scroll"]["sh"] - r["scroll"]["ch"] >= 400:
                    bad.append(f"{name} {label}: the header did not scroll away")
                if r["footLinks"] and r["footLinks"][-1]["b"] > r["docH"] + 1:
                    bad.append(f"{name} {label}: a footer link is out of reach")
        self.collect("AC-70", bad)

    def test_ac71_a_phone_meets_the_page_in_order(self):
        self.look()
        bad = []
        for name in self.users():
            r = Shell.R[name][390]
            if r["headerButtons"] or r["menuHints"] or r["backLinks"]:
                bad.append(f"{name}: a menu, search or back link in the shell")
            tops = [("brand", r["brand"]), ("balance", r["bal"]), ("steps", r["navLinks"][0]), ("tabs", r["navLinks"][2]), ("page", r["main"]), ("footer", r["footer"])]
            ys = [t[1]["y"] for t in tops if t[1]]
            if ys != sorted(ys):
                bad.append(f"{name}: order from the top is {[(t[0], round(t[1]['y'])) for t in tops if t[1]]}")
            hrefs = [l["href"] for l in r["navLinks"]]
            if hrefs[:5] != ["/profile", "/generate", "/applications", "/credits", "/account"]:
                bad.append(f"{name}: nav is {hrefs}")
            if not any(f["t"] == "Sign out" for f in r["footLinks"]):
                bad.append(f"{name}: Sign out is not in the footer")
        self.collect("AC-71", bad)

    # ----------------------------------------------------------------------------------------- the page column
    def test_ac19_the_column(self):
        self.look()
        bad = []
        for name, by_w in Shell.R.items():
            for w in (1280, 1440):
                r = by_w[w]
                c = r["column"]
                if not c:
                    continue
                if c["w"] > 880.5 or abs(c["x"] - (r["docCW"] - c["r"])) > 1.5:
                    bad.append(f"{name}@{w}: column {c['w']} wide at {c['x']}")
                if r["colBg"] not in ("rgba(0, 0, 0, 0)", GROUND):
                    bad.append(f"{name}@{w}: column background {r['colBg']}")
            if by_w[390]["brand"] and abs(by_w[390]["brand"]["x"] - 16) > 1.5:
                bad.append(f"{name}@390: gutter {by_w[390]['brand']['x']}")
            if by_w[768]["brand"] and abs(by_w[768]["brand"]["x"] - 24) > 1.5:
                bad.append(f"{name}@768: gutter {by_w[768]['brand']['x']}")
        self.collect("AC-19", bad)

    # ------------------------------------------------------------------------------------------- the header
    def test_ac22_to_24_the_header_rows(self):
        self.look()
        bad = []
        for name in self.users():
            for w in HDR:
                r = Shell.R[name][w]
                br, bal, nav, links = r["brand"], r["bal"], r["nav"], r["navLinks"]
                steps, tabs = links[:2], links[2:]
                same = lambda xs, tol: max(x["y"] for x in xs) - min(x["y"] for x in xs) <= tol
                if w >= 480:
                    if not (bal["x"] >= br["r"] and abs((bal["y"] + bal["h"] / 2) - (br["y"] + br["h"] / 2)) <= 24):
                        bad.append(f"{name}@{w}: balance is not at the right of the brand's row")
                    if nav["y"] < br["b"] - 1:
                        bad.append(f"{name}@{w}: the nav is not in row 2")
                if w >= 840:
                    if not same(links, 8):
                        bad.append(f"{name}@{w}: the nav rail is not one line")
                    xs = [l["x"] for l in links]
                    if xs != sorted(xs):
                        bad.append(f"{name}@{w}: nav items are not left to right in order")
                elif w >= 480:
                    if not same(steps, 4) or abs(steps[0]["w"] - steps[1]["w"]) > 2 or steps[0]["w"] < 0.4 * nav["w"]:
                        bad.append(f"{name}@{w}: the two steps are not half the width each on line 1")
                    if min(t["y"] for t in tabs) < steps[0]["b"] - 2:
                        bad.append(f"{name}@{w}: the tabs are not on a line below the steps")
                    if len({round(t["y"] / 10) for t in tabs}) == 1 and (tabs[0]["x"] - nav["x"] > 16 or nav["r"] - tabs[-1]["r"] > 16):
                        bad.append(f"{name}@{w}: the tab line is not filled edge to edge")
                else:
                    if bal["y"] < br["b"] - 1 or abs(bal["x"] - br["x"]) > 4 or bal["w"] < 0.85 * r["header"]["w"]:
                        bad.append(f"{name}@{w}: the balance does not take its own full-width row")
                    lines = sorted({round(t["y"] / 10) for t in tabs})
                    if name == "owner_profile" and w == 320 and not (len(lines) == 2 and sum(1 for t in tabs if round(t["y"] / 10) == lines[0]) == 2):
                        bad.append(f"{name}@{w}: the owner's tabs do not wrap two and two ({lines})")
        self.collect("AC-22 to AC-24", bad)

    def test_ac25_every_label_is_visible_and_nothing_scrolls(self):
        self.look()
        bad = []
        for name in self.users():
            for w in ALL:
                r = Shell.R[name][w]
                if r["nav"]["sw"] > r["nav"]["cw"] + 1 or r["ellipsis"] or r["headerButtons"]:
                    bad.append(f"{name}@{w}: the rail scrolls, ellipsises or hides behind a button")
                for l in r["navLinks"]:
                    if l["sw"] > l["cw"] + 1 or l["r"] > w + 0.5 or l["label"]["w"] < 10 or l["display"] == "none":
                        bad.append(f"{name}@{w}: {l['t']} is clipped or off screen")
                if r["overflow"]:
                    bad.append(f"{name}@{w}: the page scrolls sideways")
        self.collect("AC-25", bad)

    def test_ac26_tab_order_is_the_order_you_see(self):
        self.look()
        bad = []
        for name in self.users():
            for w in HDR:
                r = Shell.R[name][w]
                items = r["navDom"]
                rows = []
                for it in items:
                    cy = it["y"] + it["h"] / 2
                    for row in rows:
                        if abs(row[0] - cy) <= 14:
                            row[1].append(it)
                            break
                    else:
                        rows.append([cy, [it]])
                seen = [id(i) for _, row in sorted(rows, key=lambda x: x[0]) for i in sorted(row, key=lambda i: i["x"])]
                if seen != [id(i) for i in items]:
                    bad.append(f"{name}@{w}: seen order differs from tab order")
                for l in r["navLinks"]:
                    if l["order"] != "0" or l["position"] in ("absolute", "fixed"):
                        bad.append(f"{name}@{w}: {l['t']} is moved by CSS order or position")
        self.collect("AC-26", bad)

    def test_ac27_the_brand(self):
        self.look()
        bad = []
        for name, by_w in Shell.R.items():
            for w in (320, 1280):
                r = by_w[w]
                if not r["brand"]:
                    bad.append(f"{name}@{w}: no brand link")
                    continue
                b = r["brand"]
                if r["brandLabel"] != "Better Jobs home" or b["href"] != "/" or b["h"] < 44:
                    bad.append(f"{name}@{w}: brand link {r['brandLabel']!r} {b['h']}")
                if b["font-size"] != "22px" or any(m["fw"] != "800" for m in r["brandMarks"] if m["fs"] != "0px" and m["clip"] == "none" and m["w"] == "auto"):
                    bad.append(f"{name}@{w}: wordmark is {b['font-size']} / {b['font-weight']}")
                marks = [m for m in r["brandMarks"] if "polygon" in m["clip"]]
                ok = False
                for m in marks:
                    mt = re.match(r"matrix\(([-\d.]+), ([-\d.]+),", m["tf"] or "")
                    if m["w"] == "24px" and m["h"] == "24px" and m["bg"] == INK and mt and abs(float(mt.group(1)) - 0.9945) < 0.002 and abs(float(mt.group(2)) + 0.1045) < 0.002:
                        ok = True
                if not ok:
                    bad.append(f"{name}@{w}: no 24 px ink scrap mark tilted -6 degrees")
        self.collect("AC-27", bad)

    def test_ac28_signed_out_pages_show_the_brand_alone(self):
        self.look()
        bad = []
        outs = [k for k, w in Shell.who.items() if w == "out" and Shell.R[k][320]["bodySignedOut"]]
        self.assertTrue(outs, "no signed-out page to look at")
        for name in outs:
            for w in (320, 1280):
                r = Shell.R[name][w]
                if r["navLinks"] or r["bal"] or not r["brand"]:
                    bad.append(f"{name}@{w}: signed-out header shows {len(r['navLinks'])} nav links, balance {bool(r['bal'])}")
        self.collect("AC-28", bad)

    def test_ac29_to_32_the_nav_marks_where_you_are(self):
        self.look()
        bad = []
        for name, href in SECTION.items():
            if name not in Shell.R:
                continue
            for w in (320, 1280):
                links = Shell.R[name][w]["navLinks"]
                cur = [l for l in links if l["cur"] == "page"]
                if len(cur) != 1 or cur[0]["href"] != href:
                    bad.append(f"{name}@{w}: aria-current is on {[l['href'] for l in cur]}")
                    continue
                if cur[0]["background-color"] != INK or cur[0]["color"] != SLAB:
                    bad.append(f"{name}@{w}: the current link is {cur[0]['background-color']} / {cur[0]['color']}")
                if any(l["background-color"] == INK for l in links if l is not cur[0]):
                    bad.append(f"{name}@{w}: another link has the current fill")
                for l in links:
                    if l["opacity"] != "1" or l["dis"] or l["pointer-events"] == "none":
                        bad.append(f"{name}@{w}: {l['t']} looks or acts disabled")
        for name, want in (("profile", "done"), ("generate_notready", "1")):
            w = 390
            p = [l for l in Shell.R[name][w]["navLinks"] if l["href"] == "/profile"][0]
            c = p["circle"]
            if not c or abs(c["w"] - 24) > 0.6 or abs(c["h"] - 24) > 0.6 or float(c["border-top-left-radius"].replace("px", "") or 0) < 11.5:
                bad.append(f"{name}: the Profile step has no 24 px circle")
            elif want == "1" and (c["t"] != "1" or c["border-top-color"] != INK):
                bad.append(f"{name}: step 1 shows {c['t']!r} with border {c['border-top-color']}")
            elif want == "done" and (c["t"] not in ("✓", "✔") and "url" not in c["background-image"] or not p["hasDone"]):
                bad.append(f"{name}: a ready profile shows {c['t']!r}, (done) heard: {p['hasDone']}")
            if name == "profile" and c and c["background-color"] != SLAB:
                bad.append("profile: the current step's circle is not white")
        a = [l for l in Shell.R["owner_profile"][390]["navLinks"] if l["href"] == "/admin"]
        if not a or Shell.R["owner_profile"][390]["navLinks"][-1]["href"] != "/admin" or not a[0]["circle"] or a[0]["circle"]["background-color"] != MARIGOLD \
                or a[0]["circle"]["t"] != "A" or abs(a[0]["circle"]["w"] - 24) > 0.6:
            bad.append("admin: Admin is not last with a 24 px marigold A")
        self.collect("AC-29 to AC-32", bad)

    def test_ac33_ac34_the_balance(self):
        self.look()
        bad = []
        for name in ("profile", "profile_heavy", "credits_zero"):
            for w in (320, 390, 480, 1280):
                r = Shell.R[name][w]
                b = r["bal"]
                if not b or b["h"] < 44 or b["href"] != "/credits":
                    bad.append(f"{name}@{w}: balance link {b and b['h']}")
                    continue
                if r["balLines"] < 2 or not re.search(r"earliest expire|buy more", b["t"]):
                    bad.append(f"{name}@{w}: {r['balLines']} lines: {b['t']!r}")
                second = [k for k in r["balKids"] if re.search(r"earliest expire|buy more", k["t"]) and len(k["t"]) < 40]
                if not second or not second[-1]["vis"] or second[-1]["fs"] != "14px" or second[-1]["color"] != MUTED:
                    bad.append(f"{name}@{w}: second line {second[-1:] }")
                if b["background-color"] != SLAB or any(k["color"] in ERRORS for k in r["balKids"]):
                    bad.append(f"{name}@{w}: balance colours change ({b['background-color']})")
        z = Shell.R["credits_zero"][390]["bal"]["t"]
        if not re.search(r"^0\s*credits.*buy more", z):
            bad.append(f"zero balance reads {z!r}")
        self.collect("AC-33 and AC-34", bad)

    def test_ac35_to_38_banners(self):
        self.look()
        bad = []
        for w in (320, 390, 1280):
            r = Shell.R["profile_paused"][w]
            pb = [b for b in r["banners"] if "paused" in b["t"].lower()]
            cb = [b for b in r["banners"] if "CV" in b["t"] and "paused" not in b["t"].lower()]
            if not pb or not cb:
                bad.append(f"profile_paused@{w}: banners found {len(pb)}, {len(cb)}")
                continue
            pb, cb, h = pb[0], cb[0], r["header"]
            if abs(pb["w"] - h["w"]) > 2 or pb["buttons"] or pb["an"] != "none" or pb["sh"] > pb["ch"] + 1 or "Paused since" not in pb["t"] + "Paused since":
                bad.append(f"{w}: pause banner {pb['w']} wide, buttons {pb['buttons']}, clip {pb['sh']}>{pb['ch']}")
            if abs(pb["y"] - (h["b"] + 12)) > 1.5 or pb["b"] > cb["y"] or abs(cb["y"] - pb["b"] - 8) > 1.5 or abs(r["main"]["y"] - cb["b"] - 24) > 1.5:
                bad.append(f"{w}: banner spacing {round(pb['y'] - h['b'])}, {round(cb['y'] - pb['b'])}, {round(r['main']['y'] - cb['b'])}")
            if not cb["bold"] or not cb["link"] or cb["link"]["h"] < 44 or int(cb["link"]["font-weight"]) < 700 or "underline" not in cb["link"]["text-decoration-line"]:
                bad.append(f"{w}: CV bar link {cb['link'] and (cb['link']['h'], cb['link']['font-weight'])}")
            elif abs(cb["link"]["y"] - cb["y"]) < 40 and cb["link"]["x"] - cb["textRight"] < 7.5 and cb["textRight"] and cb["link"]["x"] > cb["textRight"] - 1:
                bad.append(f"{w}: 'Open it' is {round(cb['link']['x'] - cb['textRight'])} px from the text before it")
        for w in (320, 390, 1280):
            r = Shell.R["generate_notready"][w]
            if r["banners"] or abs(r["main"]["y"] - r["header"]["b"] - 24) > 1.5:
                bad.append(f"generate_notready@{w}: with no banner main starts {round(r['main']['y'] - r['header']['b'])} px under the header")
        self.collect("AC-35 to AC-38", bad)

    # ------------------------------------------------------------------------------------------- the footer
    def test_ac39_to_42_the_footer(self):
        self.look()
        bad = []
        for name, by_w in Shell.R.items():
            for w in (320, 390, 1280):
                r = by_w[w]
                fl = r["footLinks"]
                texts = [f["t"] for f in fl]
                signed = Shell.who[name] != "out" and r["bodySignedOut"] is False
                want = (["Report a problem", "Your reports"] if signed and "Report a problem" in texts else []) + ["Privacy notice", "Terms"] + (["Sign out"] if signed else [])
                core = [t for t in texts if not re.match(r"v\d", t)]
                if core != want and not (not signed and core == ["Privacy notice", "Terms"]):
                    bad.append(f"{name}@{w}: footer reads {texts}")
                v = r["version"]
                if not texts or not v or not re.match(r"v\d", v["t"]):
                    bad.append(f"{name}@{w}: the version is not last")
                elif v["font-size"] != "14px" or "Geist Mono" not in v["font-family"] or v["color"] != MUTED:
                    bad.append(f"{name}@{w}: the version label is {v['font-size']} {v['color']}")
                for f in fl:
                    if f["h"] < 44 or f["font-size"] != "16px" or "underline" not in f["text-decoration-line"] or f["color"] != INK:
                        bad.append(f"{name}@{w}: footer link {f['t']!r} {f['h']} {f['font-size']} {f['color']}")
                so = [f for f in fl if f["t"] == "Sign out"]
                if so and (so[0]["tag"] != "BUTTON" or so[0]["type"] != "submit" or not so[0]["inForm"] or so[0]["background-color"] != "rgba(0, 0, 0, 0)" or so[0]["border-top-width"] != "0px"):
                    bad.append(f"{name}@{w}: Sign out does not look like the links")
                if r["footer"] and r["docH"] - r["footLinks"][-1]["b"] < 48 if fl else False:
                    bad.append(f"{name}@{w}: {round(r['docH'] - fl[-1]['b'])} px below the footer")
                if r["footer"]["position"] in ("fixed", "sticky"):
                    bad.append(f"{name}@{w}: footer is fixed")
        self.collect("AC-39 to AC-42", bad)

    # ----------------------------------------------------------------------------- keyboard, touch, admin
    def test_ac43_ac44_keyboard(self):
        self.look()
        bad = []
        for name, by_w in Shell.R.items():
            for w in (320, 1280):
                r = by_w[w]
                sk = r["skipBefore"]
                if not r["firstFocusable"] or not r["firstFocusable"]["same"]:
                    bad.append(f"{name}@{w}: the skip link is not the first stop")
                    continue
                if sk and sk["x"] + sk["w"] > 1 and sk["y"] + sk["h"] > 1 and sk["w"] > 2:
                    bad.append(f"{name}@{w}: the skip link is in sight when not focused")
                a = r["skipAfter"]
                if not r["skipFocused"] or a["background-color"] != INK or a["color"] != SLAB or a["font-size"] != "16px" or int(a["font-weight"]) < 700 or a["h"] < 44 or a["y"] > 40:
                    bad.append(f"{name}@{w}: focused skip link {a and (a['background-color'], a['h'], a['y'])}")
                if r["mainRing"]["style"] != "none" and r["mainRing"]["width"] != "0px":
                    bad.append(f"{name}@{w}: main shows a ring")
                for k, ring in r["rings"].items():
                    if (ring["style"], ring["width"], ring["offset"], ring["color"]) != ("solid", "3px", "3px", INK):
                        bad.append(f"{name}@{w}: focus ring on {k} is {ring}")
        self.collect("AC-43 and AC-44", bad)

    def test_ac45_touch_targets(self):
        self.look()
        bad = []
        seen = set()
        for name, by_w in Shell.R.items():
            for w in (320, 390, 1280):
                for group, items in by_w[w]["groups"].items():
                    for it in items:
                        key = (name, w, group, it["t"], round(it["x"]), round(it["y"]))
                        if key in seen:
                            continue
                        seen.add(key)
                        if it["h"] < 43.5 or it["w"] < 43.5:
                            bad.append(f"{name}@{w} {group} {it['t']!r}: {round(it['w'])}x{round(it['h'])}")
                    for i, a in enumerate(items):
                        for b in items[i + 1:]:
                            dx = max(b["x"] - a["r"], a["x"] - b["r"], 0)
                            dy = max(b["y"] - a["b"], a["y"] - b["b"], 0)
                            if (dx or dy) and (dx * dx + dy * dy) ** 0.5 < 7.5 and group in ("nav", "foot", "btn", "pack", "check"):
                                bad.append(f"{name}@{w} {group}: {a['t']!r} and {b['t']!r} are {round((dx * dx + dy * dy) ** 0.5, 1)} px apart")
        self.collect("AC-45", bad)

    def test_ac64_admin_tables_scroll_inside_their_slab(self):
        self.look()
        bad = []
        for w in ALL:
            if 561 <= w <= 880:
                r = Shell.R["admin"][w]
                if r["overflow"]:
                    bad.append(f"admin@{w}: the page scrolls sideways")
                for t in r["tables"]:
                    if t["tr"] > t["slabR"] + 1:
                        bad.append(f"admin@{w}: a table sticks out of its slab by {round(t['tr'] - t['slabR'])} px")
        self.assertTrue(any(561 <= w <= 880 for w in ALL))
        self.collect("AC-64", bad)


if __name__ == "__main__":
    unittest.main()
