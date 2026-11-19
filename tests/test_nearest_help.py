"""Nearest help (ticket 10): which OpenStreetMap objects become a shelter, hospital, clinic and so on, and that
nothing military is ever indexed. These are the build's decisions, checked on tag sets like the ones in the real
data (counts and tags: notes/10-nearest-help.md). The page side is in tests/test_nearest_help_browser.py."""
import os
import subprocess
import unittest

from servedkit import REPO, ServedKit
from test_map_search import load_builder
from test_served_kit_browser import REQUIRED, find_chrome, why_skip


class WhatIsIndexedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kind = staticmethod(load_builder().service_kind)

    def test_every_category_is_found_by_its_tags(self):
        for tags, want in [
            ({"amenity": "hospital"}, "hospital"),
            ({"healthcare": "hospital"}, "hospital"),
            ({"amenity": "clinic"}, "clinic"),
            ({"amenity": "doctors"}, "doctors"),
            ({"healthcare": "centre"}, "clinic"),
            ({"healthcare": "doctor"}, "doctors"),
            ({"amenity": "pharmacy"}, "pharmacy"),
            ({"healthcare": "pharmacy"}, "pharmacy"),
            ({"amenity": "drinking_water"}, "drinking_water"),
            ({"amenity": "water_point"}, "water_point"),
            ({"man_made": "water_tap"}, "drinking_water"),
            ({"natural": "spring", "drinking_water": "yes"}, "drinking_water"),
            ({"man_made": "water_well", "drinking_water": "yes"}, "drinking_water"),
            ({"shop": "supermarket"}, "supermarket"),
            ({"shop": "convenience"}, "convenience"),
            ({"shop": "bakery"}, "bakery"),
            ({"shop": "butcher"}, "butcher"),
            ({"shop": "greengrocer"}, "greengrocer"),
            ({"shop": "grocery"}, "grocery"),
            ({"shop": "general"}, "general"),
            ({"amenity": "fuel"}, "fuel"),
            ({"amenity": "police"}, "police"),
            ({"amenity": "fire_station"}, "fire_station"),
            ({"emergency": "fire_station"}, "fire_station"),
        ]:
            self.assertEqual(self.kind(tags), want, str(tags))

    def test_what_is_not_help_is_left_out(self):
        for tags in [
            {"shop": "mall"}, {"shop": "department_store"}, {"shop": "deli"},
            {"natural": "spring"},                                      # a spring nobody calls drinkable
            {"man_made": "water_well"},
            {"amenity": "drinking_water", "drinking_water": "no"},
            {"man_made": "water_tap", "drinking_water": "no"},
            {"amenity": "fuel", "access": "private"},
            {"amenity": "fuel", "access": "customers"},
            {"emergency": "fire_hydrant"},
            {"emergency": "assembly_point"},
            {"amenity": "shelter", "shelter_type": "picnic_shelter"},   # a roof at a bus stop or picnic place
            {"amenity": "shelter", "shelter_type": "public_transport"},
            {"amenity": "shelter"},
            {"bunker_type": "personnel_shelter", "military": "bunker"},  # a historic dugout
        ]:
            self.assertIsNone(self.kind(tags), str(tags))

    def test_the_shelter_tags_people_use_all_make_a_shelter(self):
        for tags in [
            {"amenity": "shelter", "shelter_type": "bomb_shelter"},      # the spec tags
            {"bunker_type": "bomb_shelter"},
            {"amenity": "air_raid_shelter"},
            {"amenity": "bomb_shelter"},
            {"emergency": "air_raid_shelter"},
            {"building": "air_raid_shelter"},
            {"bunker_type": "air_raid_shelter"},
            {"bunker_type": "аir-raid shelter"},                    # a Cyrillic a, as mapped
            {"bunker_type": "civil_shelter"},                            # the civil tags
            {"building": "bomb_shelters"},
            {"amenity": "shelter", "shelter_type": "nuclear"},
            {"amenity": "shelter", "shelter_type": "radioactive_shelter"},
            {"amenity": "shelter", "shelter_type": "civil_defence"},
        ]:
            self.assertEqual(self.kind(tags), "shelter", str(tags))

    def test_the_shelter_group_names_the_tag_it_was_found_by(self):
        group = load_builder().shelter_group
        self.assertEqual(group({"bunker_type": "bomb_shelter", "military": "bunker"}), "bunker_type=bomb_shelter")
        self.assertEqual(group({"amenity": "shelter", "shelter_type": "nuclear"}), "shelter_type=nuclear")
        self.assertIsNone(group({"amenity": "hospital"}))


class NothingMilitaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kind = staticmethod(load_builder().service_kind)

    def test_a_civil_shelter_that_is_also_tagged_military_bunker_stays(self):
        # Mappers tag civil shelters with the old bunker scheme: military=bunker next to a civil shelter tag.
        self.assertEqual(self.kind({"bunker_type": "bomb_shelter", "military": "bunker"}), "shelter")
        self.assertEqual(self.kind({"bunker_type": "civil_shelter", "military": "bunker", "name": "Укриття"}), "shelter")

    def test_a_military_fixture_never_comes_out(self):
        for tags in [
            {"military": "bunker"},
            {"military": "bunker", "bunker_type": "pillbox"},
            {"military": "bunker", "bunker_type": "munitions"},
            {"military": "bunker", "bunker_type": "command"},
            {"military": "bunker", "bunker_type": "hardened_aircraft_shelter"},
            {"military": "barracks", "amenity": "hospital"},
            {"military": "yes", "amenity": "fuel"},
            {"landuse": "military", "amenity": "police"},
            {"building": "military", "amenity": "pharmacy"},
            {"office": "military", "amenity": "police"},
            {"access": "military", "amenity": "fuel"},
            {"operator:type": "military", "amenity": "hospital"},
            {"operator": "Збройні сили України", "amenity": "hospital"},
            {"operator": "Міністерство оборони", "amenity": "clinic"},
            {"name": "Військовий госпіталь", "amenity": "hospital"},
            {"name": "Військова частина А0000", "amenity": "police"},
            {"name:uk": "Магазин ТЦК", "shop": "convenience"},
            {"name": "Military hospital", "amenity": "hospital"},
            {"name": "Army shop", "shop": "general"},
            # a shelter that is military in any other way than the old bunker tag is still left out
            {"bunker_type": "bomb_shelter", "military": "barracks"},
            {"bunker_type": "civil_shelter", "landuse": "military"},
            {"bunker_type": "bomb_shelter", "military": "bunker", "operator": "Збройні сили України"},
            {"amenity": "shelter", "shelter_type": "bomb_shelter", "name": "Військове укриття"},
        ]:
            self.assertIsNone(self.kind(tags), str(tags))

    def test_a_civil_object_with_a_name_that_only_looks_military_stays(self):
        self.assertEqual(self.kind({"amenity": "pharmacy", "name": "Аптека Безсумна"}), "pharmacy")
        self.assertEqual(self.kind({"amenity": "hospital", "name": "Міська лікарня"}), "hospital")


class BorderCrossingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = load_builder()

    def test_a_crossing_on_a_closed_stretch_is_left_out(self):
        # Transnistria stands in as a square; the Ukrainian post sits 1 km outside its edge, the Moldovan one far away.
        closed = [self.b.Outline([[(30.0, 46.0), (30.5, 46.0), (30.5, 46.5), (30.0, 46.5)]])]
        near = self.b.near_closed_border
        self.assertTrue(near(30.25, 46.25, closed, 3))          # inside
        self.assertTrue(near(29.99, 46.25, closed, 3))          # about 0.8 km outside
        self.assertFalse(near(29.90, 46.25, closed, 3))         # 8 km outside
        self.assertFalse(near(29.99, 46.25, [], 3))             # no closed area in the country config

    def test_a_military_border_object_is_not_a_crossing(self):
        self.assertIsNone(self.b.crossing_object({"barrier": "border_control", "landuse": "military"}))
        self.assertIsNone(self.b.crossing_object({"barrier": "border_control", "name": "Військовий пост"}))
        tags = {"barrier": "border_control", "name": "Шегині"}
        self.assertEqual(self.b.crossing_object(tags), tags)


@unittest.skipIf(why_skip() and not REQUIRED, why_skip())
class NearestHelpInTheBrowserTest(unittest.TestCase):
    def test_every_category_and_the_shelter_note(self):
        kit = ServedKit(tiles=True)
        try:
            kit.start()
            env = dict(os.environ, EK_TEST_URL=kit.url, EK_CHROME=find_chrome())
            run = subprocess.run(["node", os.path.join(REPO, "tests", "browser", "nearest.js")], env=env, cwd=REPO,
                                 capture_output=True, text=True, timeout=240)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertGreaterEqual(run.stdout.count("ok - "), 5, run.stdout)
        finally:
            kit.stop()


if __name__ == "__main__":
    unittest.main()
