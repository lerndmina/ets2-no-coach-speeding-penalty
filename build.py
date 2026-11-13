"""Build the 'No Coach Speeding Penalty' ETS2 mod.

Reads def/bus_economy_data.sii from your own game's def.scs, changes only the
two passenger speed-penalty lines, and packs it as a ZIP .scs mod.

Usage:
  python3 build.py [PATH_TO_def.scs] [-o OUTPUT.scs]

Default def.scs: the Steam install under ~/.local/share/Steam.
"""
import argparse, os, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hashfs import HashFS

DEFAULT_DEF = os.path.expanduser(
    "~/.local/share/Steam/steamapps/common/Euro Truck Simulator 2/def.scs")
DEF_PATH = "def/bus_economy_data.sii"
EDITS = [
    ("\tsatisfaction_speed_trigger_kph: 130.0", "\tsatisfaction_speed_trigger_kph: 1000.0"),
    ("\tsatisfaction_speed_penalty: (0.09, 0.18)", "\tsatisfaction_speed_penalty: (0.0, 0.0)"),
]
MANIFEST = """SiiNunit
{
mod_package : .package_name
{
	package_version: "1.0"
	display_name: "No Coach Speeding Penalty"
	author: "lerndmina"
	category[]: "other"
	compatible_versions[]: "1.62.*"
	description_file: "description.txt"
}
}
"""
DESCRIPTION = (
    "Removes the coach passenger satisfaction penalty for driving over 130 km/h.\n"
    "Every other passenger satisfaction rule (acceleration, crashes, lateness,\n"
    "offences, rewards) is unchanged.\n\n"
    "Built from def/bus_economy_data.sii of game version 1.62. Rebuild it\n"
    "after a game update that changes that file.\n"
)

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("def_scs", nargs="?", default=DEFAULT_DEF)
ap.add_argument("-o", "--output", default="no_coach_speeding_penalty.scs")
a = ap.parse_args()

text = HashFS(a.def_scs).read(DEF_PATH).decode("utf-8")
for old, new in EDITS:
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one '{old.strip()}' in {DEF_PATH}; "
                         "the game changed this file, so check the new values before rebuilding")
    text = text.replace(old, new)

with zipfile.ZipFile(a.output, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("manifest.sii", MANIFEST)
    z.writestr("description.txt", DESCRIPTION)
    z.writestr(zipfile.ZipInfo("def/"), b"")
    z.writestr(DEF_PATH, text)
print(a.output)
