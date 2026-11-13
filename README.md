# ETS2: No Coach Speeding Penalty

A small Euro Truck Simulator 2 mod for coach jobs. Passengers stop losing
satisfaction when you drive over 130 km/h. Every other satisfaction rule
(acceleration, crashes, lateness, offences, rewards) works as before.

## How it works

Coach passenger rules live in `def/bus_economy_data.sii` inside the game's
`def.scs`. The mod overrides that file with two values changed:

| Key | Game | Mod |
|---|---|---|
| `satisfaction_speed_trigger_kph` | `130.0` | `1000.0` |
| `satisfaction_speed_penalty` | `(0.09, 0.18)` | `(0.0, 0.0)` |

The repo contains no game files. `build.py` reads `bus_economy_data.sii`
from your own install and patches it, so the mod always matches your game
version. If an update changes either line, the build stops instead of
producing a stale override.

## Build

Python 3, standard library only.

```bash
python3 build.py                       # uses the default Steam path on Linux
python3 build.py "/path/to/def.scs" -o no_coach_speeding_penalty.scs
```

Copy the `.scs` into your `Documents/Euro Truck Simulator 2/mod/` folder.
Under Proton that is
`steamapps/compatdata/227300/pfx/drive_c/users/steamuser/Documents/Euro Truck Simulator 2/mod/`.
Then enable **No Coach Speeding Penalty** in the in-game Mod Manager.

Rebuild after any game update that touches `bus_economy_data.sii`.

## `hashfs.py`

A minimal read-only reader for SCS HashFS v2 archives (`ls`, `tree`, `cat`,
`extract`). It supports plain files and directories only, and paths longer
than 64 bytes don't currently resolve.

```bash
python3 hashfs.py def.scs cat def/bus_economy_data.sii
```

Tested against game version 1.62.3.2.
