"""The map's shape and how the map download cuts to it (ticket 08).

The shape is a GeoJSON polygon in config/ (country config map.shape): Ukraine and Moldova in full plus a strip
of about 100 km into Poland, Slovakia, Hungary and Romania. The download must hand that file to `pmtiles extract`
(--region), not a rectangle (--bbox), and cut the world overview at the config's overview zoom.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from servedkit import REPO
from test_country_config import check, real

SHAPE = os.path.join(REPO, "config", "map-area.geojson")

# (name, longitude, latitude)
INSIDE = [("Sevastopol", 33.52, 44.62), ("Simferopol", 34.10, 44.95), ("Kerch", 36.47, 45.35),
          ("Donetsk", 37.80, 48.00), ("Luhansk", 39.30, 48.57), ("Mariupol", 37.55, 47.10), ("Kyiv", 30.52, 50.45),
          ("Uzhhorod", 22.29, 48.62), ("Chisinau", 28.86, 47.01), ("Tiraspol", 29.64, 46.84),
          ("Przemysl", 22.77, 49.78), ("Kosice", 21.26, 48.72), ("Debrecen", 21.63, 47.53), ("Suceava", 26.25, 47.65)]
OUTSIDE = [("Krakow", 19.94, 50.06), ("Bucharest", 26.10, 44.43), ("Minsk", 27.56, 53.90),
           ("Rostov-on-Don", 39.72, 47.23), ("Belgorod", 36.59, 50.60), ("Warsaw", 21.01, 52.23)]


def polygon():
    with open(SHAPE, encoding="utf-8") as f:
        g = json.load(f)
    feats = g["features"] if g["type"] == "FeatureCollection" else [g]
    return [f["geometry"] for f in feats]


def inside(x, y, rings):
    """Even-odd ray casting over a Polygon's rings."""
    n = 0
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                n += 1
    return n % 2 == 1


class ShapeTest(unittest.TestCase):
    def test_the_shape_is_one_polygon_and_config_names_it(self):
        geoms = polygon()
        self.assertEqual([g["type"] for g in geoms], ["Polygon"])
        self.assertEqual(real()["map"]["shape"], "config/map-area.geojson")
        self.assertEqual((real()["map"]["max_zoom"], real()["map"]["world_max_zoom"]), (15, 6))
        self.assertNotIn("bbox", real()["map"])

    def test_the_shape_takes_in_ukraine_moldova_and_a_strip_but_not_the_cities_beyond(self):
        rings = polygon()[0]["coordinates"]
        for name, x, y in INSIDE:
            self.assertTrue(inside(x, y, rings), name + " should be inside")
        for name, x, y in OUTSIDE:
            self.assertFalse(inside(x, y, rings), name + " should be outside")

    def test_the_regions_are_ukraine_moldova_in_full_and_four_border_strips(self):
        regions = {r["geofabrik"]: r["detail"] for r in real()["map"]["regions"]}
        self.assertEqual(regions, {"europe/ukraine": "full", "europe/moldova": "full", "europe/poland": "border",
                                   "europe/slovakia": "border", "europe/hungary": "border", "europe/romania": "border"})

    def test_the_validator_wants_a_shape_file_that_exists_and_is_a_polygon(self):
        self.assertEqual(check(real())[0], 0, check(real()))
        c = real(); c["map"]["shape"] = "config/nowhere.geojson"
        self.assertNotEqual(check(c)[0], 0)
        c = real(); del c["map"]["max_zoom"]
        self.assertNotEqual(check(c)[0], 0)
        with tempfile.TemporaryDirectory() as d:   # a point is not a map shape
            bad = os.path.join(d, "bad.geojson")
            with open(bad, "w") as f:
                json.dump({"type": "Point", "coordinates": [1, 2]}, f)
            c = real(); c["map"]["shape"] = bad
            code, out = check(c)
            self.assertNotEqual(code, 0)
            self.assertIn("map.shape", out)


class DownloadTest(unittest.TestCase):
    """scripts/get-maps.sh against a stand-in `pmtiles` and `curl`: what it asks for, and how it keeps the files."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ek-maps-")
        self.kit = os.path.join(self.tmp, "kit")
        for d in ("scripts", "config"):
            shutil.copytree(os.path.join(REPO, d), os.path.join(self.kit, d))
        os.makedirs(os.path.join(self.kit, "tools"))
        os.makedirs(os.path.join(self.kit, "web", "map", "data"))
        open(os.path.join(self.kit, "web", "map", "data", "places.json.gz"), "w").close()   # map search is not this ticket
        self.log = os.path.join(self.tmp, "calls.log")
        self.write_tool(os.path.join(self.kit, "tools", "pmtiles"), """#!/bin/bash
echo "$@" >> "$LOG"
[ "$1" = extract ] || exit 1
[ -n "$FAIL" ] && exit 1
printf 'PMTiles' > "$3"
""")
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(self.bin)
        self.write_tool(os.path.join(self.bin, "curl"), "#!/bin/bash\nexit 0\n")   # every daily build 'exists'

    def write_tool(self, path, text):
        with open(path, "w") as f:
            f.write(text)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def run_script(self, **extra):
        env = dict(os.environ, LOG=self.log, PATH=self.bin + os.pathsep + os.environ["PATH"], **extra)
        return subprocess.run(["bash", os.path.join(self.kit, "scripts", "get-maps.sh")], env=env, capture_output=True,
                              text=True, cwd=self.kit)

    def calls(self):
        with open(self.log) as f:
            return [line.split() for line in f]

    def test_it_cuts_to_the_shape_and_the_overview_zoom(self):
        run = self.run_script()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        world, area = self.calls()
        self.assertIn("--maxzoom=6", world)
        self.assertEqual(world[2], os.path.join(self.kit, "maps", "world.pmtiles.part"))
        self.assertIn("--region=" + os.path.join(self.kit, "config", "map-area.geojson"), area)
        self.assertIn("--maxzoom=15", area)
        self.assertFalse([a for a in area + world if a.startswith("--bbox")], "no rectangle")
        for name in ("world.pmtiles", "ukraine.pmtiles"):
            self.assertTrue(os.path.isfile(os.path.join(self.kit, "maps", name)), name)
        self.assertFalse([n for n in os.listdir(os.path.join(self.kit, "maps")) if n.endswith(".part")])

    def test_finished_files_are_skipped_and_a_stopped_cut_leaves_no_final_file(self):
        self.run_script()
        open(self.log, "w").close()
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.calls(), [])
        shutil.rmtree(os.path.join(self.kit, "maps"))
        self.assertNotEqual(self.run_script(FAIL="1").returncode, 0)
        self.assertEqual([n for n in os.listdir(os.path.join(self.kit, "maps")) if n.endswith(".pmtiles")], [])


if __name__ == "__main__":
    unittest.main()
