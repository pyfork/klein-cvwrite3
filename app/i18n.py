"""The few strings shown in Malay as well as English: the notice pages and the consent screen (PDPA s.7(3) asks
for the notice in both languages). The upload warnings show both languages at once, in profile.html. Everything else is English first (brief, Addendum 2).

The Malay is from the owner's translator (2026-10-25), except the lines marked "agent draft", which the translator
should check.
"""

LANG_NAMES = {"en": "English", "ms": "Bahasa Malaysia"}

STRINGS = {
    "en": {
        "summary_heading": "In short",
        "eyebrow": "Privacy notice v{version}",
        "first_title": "Before you start: your privacy",
        "first_lede": "cvwrite3 writes a CV for a job ad you paste. To do that, we need some of your data. Here's a summary of the notice.",
        "major_title": "We've updated our privacy notice",
        "major_lede": "Something changed about your data, so we need you to agree again before you carry on. Your CVs and credits aren't affected.",
        "read_full": "Read the full notice",
        "missing": "Tick the first box to carry on. We can't write a CV without your agreement.",
        "agree": "I've read the privacy notice and agree.",
        "sensitive": "My CV may include sensitive data (race, religion or health). I agree to it being used to write my CV.",
        "hint": "The second box is optional. Leave it unticked if your CV has none of these. Either way, we'll ask you to remove an IC number.",
        "continue": "Continue",
        "notice_title": "Privacy notice",
        "notice_lede": "How cvwrite3 collects, uses and protects your personal data, under Malaysia's Personal Data Protection Act 2010.",
        "draft": "draft",
        "older": "This is an older version.",
        "read_current": "Read the current one (v{version})",
        "all_versions": "All versions and what changed",
        "what_changed": "What changed in v{version}:",
    },
    "ms": {
        "summary_heading": "Secara ringkas",
        "eyebrow": "Notis privasi v{version}",
        "first_title": "Sebelum anda bermula: privasi anda",
        "first_lede": "cvwrite3 menulis CV untuk iklan pekerjaan yang anda tampal. Untuk berbuat demikian, kami memerlukan sebahagian data anda. Berikut ialah ringkasan notis ini.",
        "major_title": "Kami telah mengemas kini notis privasi kami",
        "major_lede": "Ada perubahan berkaitan data anda, jadi kami perlu mendapatkan persetujuan anda sekali lagi sebelum anda meneruskan. CV dan kredit anda tidak terjejas.",
        "read_full": "Baca notis penuh",
        "missing": "Tandakan kotak pertama untuk meneruskan. Kami tidak dapat menulis CV tanpa persetujuan anda.",
        "agree": "Saya telah membaca notis privasi ini dan bersetuju.",
        "sensitive": "CV saya mungkin mengandungi data peribadi sensitif (kaum, agama atau kesihatan). Saya bersetuju data itu digunakan untuk menulis CV saya.",
        "hint": "Kotak kedua adalah pilihan. Biarkan kotak itu tidak ditandakan jika CV anda tidak mengandungi mana-mana maklumat ini. Walau apa pun pilihan anda, kami akan meminta anda membuang nombor IC.",
        "continue": "Teruskan",
        # agent draft from here: the translator should check these
        "notice_title": "Notis privasi",
        "notice_lede": "Cara cvwrite3 mengumpul, menggunakan dan melindungi data peribadi anda, di bawah Akta Perlindungan Data Peribadi 2010.",
        "draft": "draf",
        "older": "Ini versi lama.",
        "read_current": "Baca versi semasa (v{version})",
        "all_versions": "Semua versi dan perubahannya",
        "what_changed": "Perubahan dalam v{version}:",
    },
}

def strings(lang):
    return STRINGS.get(lang, STRINGS["en"])
