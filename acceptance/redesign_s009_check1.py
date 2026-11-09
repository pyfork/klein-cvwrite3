"""Locked check, redesign S-009. CHECK 1: the home's frame, header and hero as their words and links (scripts off).

AC-100 (the order: the skip link, the header, the hero, its heading v2's), AC-104 (the header's links and their
targets), AC-107 (tab order), AC-109 and AC-110 (the hero's words), AC-111 and AC-117 (the picture with scripts off),
AC-161 (where links go) and AC-162 (images carry their size; the art is decorative), and the plan's phone budget for
the home. The words are v2's (acceptance/fixtures/s009_v2_text.json).
Fails before the work: `/` with the setting on serves slice 8's placeholder, which has no section links and no hero.
senior-lead-Opus5.5-agent, 2026-11-08 (cut from the top half's draft on branch draft-redesign-top-half, 3411036)
"""
import json
import re
import unittest

import redesign_s009_common as H

FIX = H.FIX

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
out.hrefs = [...doc.querySelectorAll('a[href]')].map(a => a.getAttribute('href'));
out.ids = [...doc.querySelectorAll('[id]')].map(e => e.id);
out.imgs = [...doc.querySelectorAll('img')].map(i => ({src: i.getAttribute('src'), w: i.getAttribute('width'), h: i.getAttribute('height'), alt: i.getAttribute('alt')}));
return out;
"""


def page_js():
    h = FIX["hero"]
    return PAGE_JS % {"picwords": json.dumps(h["picture_words"]), "photocopy": json.dumps(h["photocopy_name"]),
                      "cap_on": json.dumps(h["caption_on"]), "cap_off": json.dumps(h["caption_off"])}


class ThePage(unittest.TestCase):
    """The frame, the header and the hero: words, links and states, read in Chrome with scripts off, at 1280 and 390."""

    @classmethod
    def setUpClass(cls):
        cls.page = H.home_html()
        with H.Site(cls.page) as site:
            got = H.measure(site, [(1280, 900), (390, 844)], page_js())
        cls.wide, cls.narrow = got[(1280, 900)], got[(390, 844)]

    def test_ac100_skip_link_header_then_hero(self):
        self.assertTrue(self.wide["header_before_h1"], "the header comes before the hero")
        self.assertEqual(self.wide["heads"][:1], FIX["headings"])
        self.assertEqual(self.wide["main_id"], "main")
        self.assertEqual(self.wide["skip"], ["Skip to content", "#main"])

    def test_ac104_the_header_links(self):
        self.assertEqual(self.wide["brand"][0], "/")
        self.assertIn("Better Jobs", self.wide["brand"][1])
        self.assertEqual(self.wide["header_links"][1:], FIX["header"]["links"] + [FIX["header"]["start"]])

    def test_ac105_ac107_tab_order(self):
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

    def test_ac161_where_links_go(self):
        ids = set(self.wide["ids"])
        self.assertTrue(self.wide["hrefs"], "the page has links")
        for href in self.wide["hrefs"]:
            with self.subTest(href=href):
                if href.startswith("#"):
                    if href[1:] not in H.LATER_IDS:
                        self.assertIn(href[1:], ids, "an in-page link has its target")
                else:
                    self.assertIn(href, ("/", "/signin", "/privacy", "/terms"), "nothing else leaves the page")

    def test_ac162_images_carry_their_size_and_decorative_alt(self):
        self.assertTrue(self.wide["imgs"], "the hero shows its art")
        for i in self.wide["imgs"]:
            with self.subTest(src=i["src"]):
                self.assertTrue((i["w"] or "").isdigit() and (i["h"] or "").isdigit(), "width and height attributes")
                self.assertEqual(i["alt"], "", "the hero's art is decorative")


class TheBudget(unittest.TestCase):
    """The plan's phone budget for the home (not an AC): the page and every file it loads, at most 900,000 bytes
    uncompressed. Set on the whole home in slice 9; slices 10 to 12 must stay inside it (going over is a re-plan)."""
    LIMIT = 900_000

    def test_budget_the_home_and_what_it_loads(self):
        page = H.home_html()
        self.assertIn(FIX["hero"]["h1"], H.norm(re.sub(r"<[^>]+>", "", page)), "the home, not the placeholder")
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
