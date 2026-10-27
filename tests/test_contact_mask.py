"""Emails, phones and profile links never reach the AI, typed in the profile or not. Made-up values only."""
import unittest

from render import contact

TEXT = """# Test Person
Shah Alam · test@example.com · +60 12-000 0000 · linkedin.com/in/test-person
Mobile 012-345 6789, office 03-1234 5678, Kuching 082-123456, (+60) 19 876 5432, 60123456789
UK +44 20 7946 0958 · https://github.com/tperson
Jan 2019 - Dec 2023 · 2019-2023 · 01/2020 – 03/2022 · 09-2019 to 12-2021 · RM 1,200,000 · 50450 Kuala Lumpur
Grew revenue 35% to RM 12.5 million; 0.5 FTE; team of 12; ISO 9001:2015; 60 people; ref 6000123
"""
KEPT = ("Jan 2019 - Dec 2023 · 2019-2023 · 01/2020 – 03/2022 · 09-2019 to 12-2021 · RM 1,200,000 · 50450 Kuala Lumpur",
        "Grew revenue 35% to RM 12.5 million; 0.5 FTE; team of 12; ISO 9001:2015; 60 people; ref 6000123", "Shah Alam")


class Mask(unittest.TestCase):
    def test_untyped_contact_is_taken_out(self):
        masked, counts = contact.mask(TEXT, {})
        for value in ("test@example.com", "12-000 0000", "345 6789", "1234 5678", "082-123456", "876 5432",
                      "60123456789", "7946 0958", "test-person", "tperson"):
            self.assertNotIn(value, masked)
        self.assertEqual(counts, {"email": 1, "phone": 7, "link": 2})

    def test_dates_money_and_counts_stay(self):
        masked, _ = contact.mask(TEXT, {})
        for line in KEPT:
            self.assertIn(line, masked)

    def test_typed_name_too(self):
        masked, counts = contact.mask(TEXT, {"name": "Test Person"})
        self.assertIn("# [name]", masked)
        self.assertEqual(counts["name"], 1)

    def test_found_lists_what_mask_takes_out_once_each(self):
        found = contact.found(TEXT + "test@example.com\n", {"name": "Test Person"})
        self.assertEqual(found[:3], [("name", "Test Person"), ("email", "test@example.com"), ("phone", "+60 12-000 0000")])
        self.assertEqual(len(found), len(set(found)))
        self.assertIn(("link", "https://github.com/tperson"), found)

    def test_guess_takes_the_first_of_each(self):
        self.assertEqual(contact.guess(TEXT), {"email": "test@example.com", "phone": "+60 12-000 0000",
                                               "links": "linkedin.com/in/test-person"})
        self.assertEqual(contact.guess("No contact here. " * 20), {})

    def test_guess_name_takes_a_first_line_that_reads_like_a_name(self):
        for text, name in (("# Test Person\nShah Alam", "Test Person"), ("**Lim Wei Jie**\n", "Lim Wei Jie"), ("---\nJohn Tan", "John Tan"),
                           ("NURUL AIN BINTI ZAKARIA\n012", "NURUL AIN BINTI ZAKARIA"), ("Kumar a/l Raman\n", "Kumar a/l Raman"),
                           ("Ahmad bin Ali", "Ahmad bin Ali"), ("Dr. Mary-Ann O'Connor", "Dr. Mary-Ann O'Connor")):
            self.assertEqual(contact.guess_name(text), name, text)

    def test_guess_name_leaves_anything_else_for_the_user(self):
        for text in ("Curriculum Vitae\nTest Person", "Resume", "test@example.com\nTest Person", "Test", "Test Person 2024",
                     "Built a daily SQL report", "Skills: SQL, Excel", "https://example.com/x", "Seven Words Is Too Many For Name",
                     "A very long line " * 6, "lowercase name here", ""):
            self.assertEqual(contact.guess_name(text), "", text)


if __name__ == "__main__":
    unittest.main()
