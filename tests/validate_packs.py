"""Validate all curated REDUX manifests without accessing game files."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
expected = {"sakura-dream", "neon-night", "frostbite", "crimson"}
found = {p.parent.name for p in (ROOT / "packs").glob("*/manifest.json")}
assert found == expected, (found, expected)

for pack_id in sorted(expected):
    path = ROOT / "packs" / pack_id / "manifest.json"
    pack = json.loads(path.read_text(encoding="utf-8"))
    assert pack["schema"] == "nameless-redux-pack-v1"
    assert pack["id"] == pack_id
    assert pack["game"]["steam_app_id"] == 4262460
    assert pack["status"] == "concept-not-installable"
    install = pack["installation"]
    assert install["supported"] is False
    assert install["method"] is None
    assert install["writes_game_files"] is False
    assert install["requires_official_mod_support"] is True
    components = pack["components"]
    assert len(components) == 8
    assert {item["type"] for item in components} == {
        "environment", "weapon_skins", "audio", "particles",
        "vehicle_skins", "outfits", "masks", "backpacks",
    }
    garage = pack["cosmetic_garage"]
    assert garage["preview"] == "original-qt-vector-concept"
    assert garage["mixable_slots"] == [
        "weapon", "vehicle", "outfit", "mask", "backpack"
    ]
    assert garage["game_asset_files_included"] is False
    assert all(item["status"] == "design" for item in components)
    performance = pack["performance"]
    assert 0 < performance["max_particle_count_per_impact"] <= 12
    assert 0 < performance["particle_lifetime_seconds"] <= 0.65
    assert 0 < performance["texture_resolution_target"] <= 1024
    assert performance["fps_gain_claimed"] is False
    assert performance["benchmarked"] is False
    assert all(pack["safety"].values())
print("All four REDUX pack manifests and all 20 cosmetic concepts validated")
