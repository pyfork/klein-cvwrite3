"""Locked check, redesign S-008. CHECK 1: the flag, and the home's top half as its words and links (scripts off).

AC-185 (production refuses the setting on), AC-186 (with it on, a visitor with no session cookie gets the home; a cookie
goes through today's checks), and what the top half holds: AC-100 (its order and headings), AC-104 (the header's links),
AC-107 (tab order), AC-109 and AC-110 (the hero's words), AC-111 and AC-117 (the picture with scripts off), AC-123 to
AC-125 and AC-131 (the three samples' panels with scripts off), AC-132 (the note), AC-133 to AC-136 (the keywords),
AC-161 (where links go) and AC-162 (images). The words are v2's (acceptance/fixtures/s008_v2_text.json).
Fails before the work: there is no `home` setting, so the settings load `CVWRITE_HOME=on` in production and the home
does not exist.
senior-lead-Opus5.5-agent, 2026-11-07
"""
import re
import unittest

import redesign_s008_common as H

FIX = H.FIX


def env(**kw):
    base = {"CVWRITE_ENV": "dev", "CVWRITE_DATABASE_URL": "postgresql://x/y", "CVWRITE_OWNER_EMAIL": "owner@example.com",
            "CVWRITE_SECRET_KEY": "x" * 40, "CVWRITE_APP_ORIGIN": "https://cvwrite3.test", "CVWRITE_CLAUDE": "real"}
    if kw.get("CVWRITE_ENV") == "prod":
        base.update(CVWRITE_SMTP_HOST="smtp.example.com", CVWRITE_SMTP_USER="u", CVWRITE_SMTP_PASSWORD="p",
                    CVWRITE_MAIL_FROM="Better Jobs <signin@example.com>")
    base.update({k: v for k, v in kw.items() if v is not None})
    return base


class TheSetting(unittest.TestCase):
    """AC-185: production refuses CVWRITE_HOME=on and any value but on or off; dev takes on and off."""

    def load(self, **kw):
        from app import config
        return config.load(env(**kw))

    def test_ac185_production_refuses_on_and_odd_values(self):
        from app import config
        for value in ("on", "ON", "yes", "1", "maybe"):
            with self.subTest(value=value):
                with self.assertRaises(config.ConfigError) as e:
                    self.load(CVWRITE_ENV="prod", CVWRITE_HOME=value)
                self.assertIn("CVWRITE_HOME", str(e.exception))

    def test_ac185_production_takes_off_and_unset(self):
        self.assertIs(self.load(CVWRITE_ENV="prod", CVWRITE_HOME="off").home, False)
        self.assertIs(self.load(CVWRITE_ENV="prod").home, False)

    def test_ac185_dev_takes_on_and_off_only(self):
        from app import config
        self.assertIs(self.load(CVWRITE_HOME="on").home, True)
        self.assertIs(self.load(CVWRITE_HOME="off").home, False)
        self.assertIs(self.load().home, False)
        with self.assertRaises(config.ConfigError) as e:
            self.load(CVWRITE_HOME="yes")
        self.assertIn("CVWRITE_HOME", str(e.exception))


class TheRoute(H.HomeCase):
    """AC-186: with the setting on, no cookie gets the home; a cookie goes through today's checks."""

    def test_ac186_no_cookie_gets_the_home(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["content-type"].startswith("text/html"))
        self.assertEqual(r.headers.get("cache-control"), "private, no-store")
        self.assertNotIn("set-cookie", {k.lower() for k in r.headers.keys()})
        self.assertIn(FIX["hero"]["h1"], H.norm(re.sub(r"<[^>]+>", "", r.text)))
        with self.conn() as c:
            self.assertEqual(c.execute("select count(*) n from sessions").fetchone()["n"], 0)

    def test_ac186_a_cookie_goes_through_todays_checks(self):
        junk = {"Cookie": "cvwrite3=not-a-session"}
        self.assertEqual((lambda r: (r.status_code, r.headers.get("location")))(self.client.get("/", headers=junk)), (303, "/signin"))
        cookie = self.as_user("ended@example.com")
        with self.conn() as c:
            c.execute("update sessions set expires_at = now() - interval '1 second'")
        r = self.client.get("/", headers=cookie)
        self.assertEqual((r.status_code, r.headers.get("location")), (303, "/signin"))
        r = self.get("/", "stranger@example.com")
        self.assertEqual((r.status_code, r.headers.get("location")), (303, "/request"))
        self.approve("nadia@example.com")
        self.agree("nadia@example.com")
        r = self.get("/", "nadia@example.com")
        self.assertEqual((r.status_code, r.headers.get("location")), (303, "/profile"))


PAGE_JS = r"""
const out = {};
const hd = header(doc);
out.header_before_h1 = !!hd && !!heads(doc)[0] && !!(hd.compareDocumentPosition(heads(doc)[0]) & 4);
out.heads = heads(doc).map(T);
out.main_id = (doc.querySelector('main') || {}).id || null;
out.skip = (() => { const f = focusables(doc)[0]; return f ? [T(f), f.getAttribute('href')] : null; })();
out.tab = focusables(doc).slice(0, 9).map(e => [T(e), e.getAttribute('href')]);
const navs = hd ? [...hd.querySelectorAll('a[href]')] : [];
out.header_links = navs.filter(shown).map(a => [T(a), a.getAttribute('href')]);
out.brand = hd && hd.querySelector('a[href]') ? [hd.querySelector('a[href]').getAttribute('href'), T(hd.querySelector('a[href]'))] : null;
const h1 = doc.querySelector('h1');
const hero = h1 && h1.closest('section');
out.h1 = T(h1);
out.hero_text = hero ? T(hero) : '';
out.hero_links = hero ? [...hero.querySelectorAll('a[href]')].filter(shown).map(a => [T(a), a.getAttribute('href')]) : [];
out.hero_li = hero ? [...hero.querySelectorAll('li')].filter(shown).map(T) : [];
const pic = hero ? [...hero.querySelectorAll('[role="img"]')] : [];
out.pictures = pic.map(p => p.getAttribute('aria-label'));
out.pic_words_shown = pic[0] ? %(picwords)s.map(w => [w, shownText(pic[0], w)]) : [];
out.photocopy_shown = pic[0] ? shownText(pic[0], %(photocopy)s) : null;
out.switch_shown = hero ? [...hero.querySelectorAll('[role="switch"]')].some(shown) : null;
out.tryit_shown = hero ? shownText(hero, 'Try it') : null;
out.cap_on = hero ? shownText(hero, %(cap_on)s) : null;
out.cap_off = hero ? shownText(hero, %(cap_off)s) : null;
const band = section(doc, %(band)s);
out.band = !!band;
if (band) {
  out.tablist_shown = [...band.querySelectorAll('[role="tablist"], [role="tab"]')].some(shown);
  out.slider_shown = [...band.querySelectorAll('[role="slider"]')].some(shown);
  out.drag_shown = shownText(band, 'Drag');
  out.tags_shown = [...band.querySelectorAll('button')].filter(b => ['Before', 'After'].includes(T(b))).some(shown);
  out.note = (() => { const n = leafWith(band, %(note)s).filter(shown)[0]; if (!n) return null;
    const panels = [...band.querySelectorAll('[id]')].filter(e => e !== band);
    return {italic: cs(n).fontStyle === 'italic', last: panels.every(p => p.contains(n) || !!(p.compareDocumentPosition(n) & 4))}; })();
}
const words = section(doc, %(words)s);
out.words = !!words;
if (words) {
  out.words_text = T(words);
  out.summary_shown = %(summary)s.map(s => shownText(words, s));
  out.people = %(people)s.map(p => {
    const link = [...words.querySelectorAll('a[href]')].find(a => T(a) === p.link);
    let blk = link; while (blk && blk !== words && !(T(blk).includes(p.head.split(' · ')[0]) && leafWith(blk, 'Before').length && leafWith(blk, 'After').length)) blk = blk.parentElement;
    if (!link || !blk || blk === words) return {found: false};
    const side = el => { for (let n = el; n && n !== blk; n = n.parentElement) { if (leafWith(n, 'Before').length && !leafWith(n, 'After').length) return 'before'; if (leafWith(n, 'After').length && !leafWith(n, 'Before').length) return 'after'; } return null; };
    const kws = p.after.stickers.map(s => s[0]);
    const stickers = [...blk.querySelectorAll('*')].filter(e => kws.includes(T(e)) && shown(e) && ![...e.children].some(c => kws.includes(T(c))));
    const bands = leafWith(blk, 'First 50 words').filter(shown).map(l => l.parentElement);
    const where = e => { const r = e.getBoundingClientRect(); const b = bands.find(x => x.contains(e) || (side(x) === side(e)));
      if (!b) return 'none'; const z = b.getBoundingClientRect(); const cy = r.top + r.height / 2; return cy >= z.top && cy <= z.bottom ? 'zone' : (cy > z.bottom ? 'out' : 'above'); };
    const rects = stickers.map(e => e.getBoundingClientRect());
    let overlap = 0; for (let i = 0; i < rects.length; i++) for (let j = i + 1; j < rects.length; j++) { const a = rects[i], b = rects[j];
      if (Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1) overlap++; }
    return {found: true, text: T(blk), href: link.getAttribute('href'), firsts: bands.length,
      before: stickers.filter(e => side(e) === 'before').map(e => [T(e), where(e)]).sort(),
      after: stickers.filter(e => side(e) === 'after').map(e => [T(e), where(e)]).sort(), overlap};
  });
}
out.panels = (out.people || []).map(p => { if (!p.href || !p.href.startsWith('#')) return null;
  const el = doc.getElementById(p.href.slice(1)); if (!el) return null;
  const after = [...el.querySelectorAll('*')].filter(e => SQ(T(e)).includes(SQ(%(afters)s[(out.people || []).indexOf(p)])));
  const deepest = after.filter(e => !after.some(o => o !== e && e.contains(o)))[0];
  let whole = false;
  if (deepest && shown(deepest)) { deepest.scrollIntoView({block: 'center'}); const r = deepest.getBoundingClientRect();   // clear of the sticky header
    const pts = [[.1, .3], [.5, .3], [.9, .3], [.1, .6], [.9, .6], [.5, .8]].map(([x, y]) => [r.left + r.width * x, r.top + r.height * y]);
    whole = pts.filter(([x, y]) => y > 0 && y < H).every(([x, y]) => { const hit = doc.elementFromPoint(x, y); return hit && (deepest.contains(hit) || hit === deepest); }); }
  return {inBand: !!band && band.contains(el), text: T(el), after_whole: whole, metres: (() => { const re = /^Top 3 keywords: \d of 3 before, \d of 3 after, from word \d+$/; const m = [...el.querySelectorAll('*')].filter(e => shown(e) && re.test(T(e)));
    return m.filter(e => !m.some(o => o !== e && e.contains(o))).map(T); })()}; });
out.hrefs = [...doc.querySelectorAll('a[href]')].map(a => a.getAttribute('href'));
out.ids = [...doc.querySelectorAll('[id]')].map(e => e.id);
out.imgs = [...doc.querySelectorAll('img')].map(i => ({src: i.getAttribute('src'), w: i.getAttribute('width'), h: i.getAttribute('height'), alt: i.getAttribute('alt')}));
return out;
"""


def page_js():
    import json
    f = FIX
    return PAGE_JS % {
        "picwords": json.dumps(f["hero"]["picture_words"]), "photocopy": json.dumps(f["hero"]["photocopy_name"]),
        "cap_on": json.dumps(f["hero"]["caption_on"]), "cap_off": json.dumps(f["hero"]["caption_off"]),
        "band": json.dumps(f["headings"][1]), "note": json.dumps(f["band_note"]), "words": json.dumps(f["headings"][2]),
        "summary": json.dumps(f["keywords"]["summary"]), "people": json.dumps(f["keywords"]["people"]),
        "afters": json.dumps([s["after"] for s in f["samples"]]),
    }


class ThePage(unittest.TestCase):
    """The top half's words, links and states, read in Chrome with scripts off, at 1280 and at 390."""

    @classmethod
    def setUpClass(cls):
        cls.page = H.home_html()
        with H.Site(cls.page) as site:
            got = H.measure(site, [(1280, 900), (390, 844)], page_js())
        cls.wide, cls.narrow = got[(1280, 900)], got[(390, 844)]

    def test_ac100_the_top_half_in_order(self):
        self.assertTrue(self.wide["header_before_h1"], "the header comes before the hero")
        self.assertEqual(self.wide["heads"][:3], FIX["headings"])
        self.assertEqual(self.wide["main_id"], "main")
        self.assertEqual(self.wide["skip"], ["Skip to content", "#main"])

    def test_ac104_the_header_links(self):
        self.assertEqual(self.wide["brand"][0], "/")
        self.assertIn("Better Jobs", self.wide["brand"][1])
        links = self.wide["header_links"][1:]
        self.assertEqual(links, FIX["header"]["links"] + [FIX["header"]["start"]])

    def test_ac107_tab_order(self):
        want = [["Skip to content", "#main"], self.wide["header_links"][0]] + FIX["header"]["links"] + [FIX["header"]["start"]]
        self.assertEqual(self.wide["tab"][:9], want)
        self.assertEqual(self.narrow["tab"][:3], [["Skip to content", "#main"], self.narrow["header_links"][0], FIX["header"]["start"]])

    def test_ac109_ac110_the_hero_words(self):
        hero = FIX["hero"]
        self.assertEqual(self.wide["h1"], hero["h1"])
        self.assertIn(hero["lede"], self.wide["hero_text"])
        self.assertEqual(self.wide["hero_links"][:2], [[hero["pills"][0][0], "/signin"], hero["pills"][1]])
        self.assertEqual(self.wide["hero_li"][:3], hero["ticks"])

    def test_ac111_ac117_the_picture_with_scripts_off(self):
        self.assertEqual(self.wide["pictures"], [FIX["hero"]["picture_label"]], "one picture, with v2's description")
        hidden = [w for w, ok in self.wide["pic_words_shown"] if not ok]
        self.assertEqual(hidden, [], "every ad's words and every cut CV's keywords show")
        self.assertFalse(self.wide["photocopy_shown"], "the photocopies are not shown: the CVs are cut to fit")
        self.assertFalse(self.wide["switch_shown"], "no switch with scripts off")
        self.assertFalse(self.wide["tryit_shown"], "no 'Try it' with scripts off")
        self.assertTrue(self.wide["cap_on"], "the caption is the 'on' caption")
        self.assertFalse(self.wide["cap_off"])

    def test_ac131_three_panels_one_after_another(self):
        self.assertTrue(self.wide["band"])
        self.assertFalse(self.wide["tablist_shown"], "no tab list with scripts off")
        self.assertFalse(self.wide["slider_shown"], "no grip")
        self.assertFalse(self.wide["drag_shown"], "no 'Drag' label")
        self.assertFalse(self.wide["tags_shown"], "no Before or After tags")
        self.assertEqual(len([p for p in self.wide["panels"] if p and p["inBand"]]), 3)

    def test_ac123_ac124_ac125_each_panel_holds_its_sample(self):
        for s, p in zip(FIX["samples"], self.wide["panels"]):
            with self.subTest(sample=s["tabTitle"]):
                text = H.squash(p["text"])
                for piece in [s["tabTitle"], s["tabLine"], *s["clipParts"], "What we found in the ad", "Top 3 keywords",
                              *[x for pq in s["problems"] for x in pq], *s["chips"], s["after"], s["before"]]:
                    self.assertIn(H.squash(piece), text, piece[:60])
                self.assertEqual(p["metres"], [s["meter"]])
                self.assertTrue(p["after_whole"], "the 'after' sheet shows whole")

    def test_ac132_the_note_ends_the_band(self):
        self.assertIsNotNone(self.wide["note"], "the made-up note is shown")
        self.assertTrue(self.wide["note"]["italic"])
        self.assertTrue(self.wide["note"]["last"], "it comes after the panels")

    def test_ac133_ac134_the_keywords(self):
        kw = FIX["keywords"]
        self.assertIn(kw["lede"], self.wide["words_text"])
        self.assertEqual(self.wide["summary_shown"], [True, True])
        for want, got in zip(kw["people"], self.wide["people"]):
            with self.subTest(person=want["head"]):
                self.assertTrue(got["found"], "the person's block, with its link")
                for piece in (want["head"], want["before"]["note"], want["after"]["note"]):
                    self.assertIn(H.squash(piece), H.squash(got["text"]))
                self.assertEqual(got["firsts"], 2, "a 'First 50 words' band on each page")
                self.assertEqual(got["before"], sorted([k, z] for k, z, _ in want["before"]["stickers"]))
                self.assertEqual(got["after"], sorted([k, z] for k, z, _ in want["after"]["stickers"]))
                self.assertEqual(got["overlap"], 0, "a sticker never covers another")

    def test_ac135_see_cv_links_to_that_panel(self):
        for i, (p, panel) in enumerate(zip(self.wide["people"], self.wide["panels"])):
            with self.subTest(person=i):
                self.assertTrue(p["href"].startswith("#"))
                self.assertIsNotNone(panel, "the link's target exists")
                self.assertIn(H.squash(FIX["samples"][i]["tabTitle"]), H.squash(panel["text"]))
                for j, other in enumerate(FIX["samples"]):
                    if j != i:
                        self.assertNotIn(H.squash(other["clipParts"][0]), H.squash(panel["text"]), "that sample's panel only")

    def test_ac136_sticker_places_are_in_the_html(self):
        # measured with scripts off: the places come from the HTML and the stylesheet alone
        for got in self.wide["people"]:
            self.assertTrue(got["found"])
            self.assertTrue(all(z in ("zone", "out") for _, z in got["before"] + got["after"]))

    def test_ac161_where_links_go(self):
        ids = set(self.wide["ids"])
        for href in self.wide["hrefs"]:
            with self.subTest(href=href):
                if href.startswith("#"):
                    if href[1:] not in H.SLICE9_IDS:
                        self.assertIn(href[1:], ids, "an in-page link has its target")
                else:
                    self.assertIn(href, ("/", "/signin", "/privacy", "/terms"), "nothing else leaves the page")

    def test_ac162_images_carry_their_size_and_decorative_alt(self):
        self.assertTrue(self.wide["imgs"], "the top half shows its art")
        for i in self.wide["imgs"]:
            with self.subTest(src=i["src"]):
                self.assertTrue((i["w"] or "").isdigit() and (i["h"] or "").isdigit(), "width and height attributes")
                self.assertEqual(i["alt"], "", "the top half's art is decorative")


class TheBudget(unittest.TestCase):
    """The plan's phone budget for the home (not an AC): the page and every file it loads, at most 900,000 bytes
    uncompressed. Set on the whole home in slice 8; slices 9 and 10 must stay inside it (going over is a re-plan)."""
    LIMIT = 900_000

    def test_budget_the_home_and_what_it_loads(self):
        page = H.home_html()
        files = set(re.findall(r'(?:src|href)="(/(?:static|fonts)/[^"?#]+)', page))
        for _, css in H.linked_sheets(page):
            files |= set(re.findall(r"url\(\s*[\"']?(/(?:static|fonts)/[^\"')?#]+)", css))
        total = len(page.encode("utf-8"))
        for f in sorted(files):
            base = H.C.STATIC if f.startswith("/static/") else H.C.FONTS
            path = base / f.split("/", 2)[2]
            self.assertTrue(path.is_file(), f"the home loads {f}, which does not exist")
            total += path.stat().st_size
        print(f"the home and what it loads: {total:,} bytes ({len(files)} files)")
        self.assertLessEqual(total, self.LIMIT)


if __name__ == "__main__":
    unittest.main()
