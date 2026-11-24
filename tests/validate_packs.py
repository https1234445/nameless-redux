"""Validate shipped REDUX pack metadata without touching any game installation."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "packs" / "sakura-dream" / "manifest.json"
pack = json.loads(path.read_text(encoding="utf-8"))
assert pack["schema"] == "nameless-redux-pack-v1"
assert pack["id"] == "sakura-dream"
assert pack["game"]["steam_app_id"] == 4262460
assert pack["status"] == "concept-not-installable"
install = pack["installation"]
assert install["supported"] is False
assert install["method"] is None
assert install["writes_game_files"] is False
assert install["requires_official_mod_support"] is True
components = pack["components"]
assert len(components) == 4
assert {item["type"] for item in components} == {
    "environment", "weapon_skins", "audio", "particles"
}
assert all(item["status"] == "design" for item in components)
performance = pack["performance"]
assert performance["max_particle_count_per_impact"] <= 12
assert 0 < performance["particle_lifetime_seconds"] <= 0.65
assert performance["texture_resolution_target"] <= 1024
assert performance["fps_gain_claimed"] is False
assert performance["benchmarked"] is False
assert all(pack["safety"].values())
print("Sakura pack metadata validation passed")
