"""NPC: жителі міста, квестодавці, торговці."""
from functools import lru_cache

from game.config import load_json
from game.entities.entity import Entity

MARKERS = {"new": ("!", "quest_new"), "ready": ("?", "quest_done")}


@lru_cache(maxsize=1)
def npc_defs() -> dict:
    return load_json("npcs.json")["npcs"]


class NPC(Entity):
    def __init__(self, npc_id: str, x: int, y: int):
        data = npc_defs()[npc_id]
        super().__init__(data["name"], x, y, "&", "npc", 1000, 0, 0)
        self.npc_id = npc_id
        self.title = data.get("title", "")

    @property
    def data(self) -> dict:
        return npc_defs()[self.npc_id]

    def set_marker(self, marker: str | None) -> None:
        """Над квестодавцем з'являється ! (новий квест) або ? (можна здати)."""
        self.glyph, self.color = MARKERS.get(marker, ("&", "npc"))


def populate_npcs(state) -> None:
    """Розставляє NPC: у будівлях міста та на вулицях (позиція відносно центру)."""
    tilemap = state.tilemap
    sx, sy = tilemap.spawn
    for npc_id, data in npc_defs().items():
        if "building" in data:
            building = tilemap.building(data["building"])
            if building is None:
                continue
            x, y = building.spot
        else:
            dx, dy = data["pos"]
            x, y = sx + dx, sy + dy
        if tilemap.is_walkable(x, y) and state.entity_at(x, y) is None:
            state.entities.append(NPC(npc_id, x, y))