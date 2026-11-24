"""Inventory: gold, item stacks, weapons, trophies, chest storage.

Items live flat in data/items.json; anything unknown is treated as a generic
"misc" trophy/material so new JSON entries work with zero code changes.
Categories follow the spec: money (gold), weapons, trophies, materials.
"""

from __future__ import annotations

from .models import Item, Weapon

CATEGORIES = ("weapons", "trophies", "materials", "misc")


class ItemStack:
    """A stack of identical items occupying one grid slot."""

    def __init__(self, item_id: str, name: str, kind: str, qty: int = 1,
                 sprite: str = "") -> None:
        self.item_id = item_id
        self.name = name
        self.kind = kind            # trophy | material | consumable | misc
        self.qty = qty
        self.sprite = sprite

    def add(self, n: int = 1) -> None:
        self.qty += n

    def take(self, n: int = 1) -> bool:
        """Remove n from the stack; True if anything was removed."""
        if self.qty <= 0 or n <= 0:
            return False
        self.qty -= n
        return True

    def to_json(self) -> dict:
        return {"id": self.item_id, "qty": self.qty}

    @classmethod
    def from_json(cls, d: dict, defs: dict) -> "ItemStack":
        iid = d.get("id", "?")
        dd = defs.get(iid, {})
        return cls(iid, dd.get("name", iid), dd.get("kind", "misc"),
                   int(d.get("qty", 1)), dd.get("sprite", ""))


class Inventory:
    """Owns everything the player carries. Shared via GameState only."""

    def __init__(self) -> None:
        self.gold: int = 50
        self.items: list[ItemStack] = []   # consumables/materials/trophies
        self.weapons: dict[str, Weapon] = {}
        self.collected_bosses: list[str] = []  # trophy room source
        self.equipped: str | None = None

    # -- weapons ------------------------------------------------------------
    def add_or_get_weapon(self, wid: str, data: dict) -> Weapon:
        if wid not in self.weapons:
            self.weapons[wid] = Weapon(
                id=wid, name=data["name"], damage=data["damage"],
                cost_per_level=data.get("cost_per_level", 20))
        return self.weapons[wid]

    def equip(self, wid: str) -> None:
        if wid in self.weapons:
            self.equipped = wid

    def equipped_weapon(self) -> Weapon | None:
        return self.weapons.get(self.equipped) if self.equipped else None

    # -- item stacks ----------------------------------------------------------
    def add_item(self, item_id: str, qty: int = 1, defs: dict | None = None
                 ) -> None:
        """Add qty of an item (stacking onto an existing slot or new one)."""
        defs = defs or {}
        for st in self.items:
            if st.item_id == item_id:
                st.add(qty)
                return
        d = defs.get(item_id, {})
        self.items.append(ItemStack(item_id, d.get("name", item_id),
                                    d.get("kind", "misc"), qty,
                                    d.get("sprite", "")))

    def remove_item(self, item_id: str, qty: int = 1) -> int:
        """Remove up to qty; returns how many were actually removed."""
        removed = 0
        for st in list(self.items):
            if st.item_id == item_id and removed < qty:
                can = min(st.qty, qty - removed)
                st.take(can)
                removed += can
                if st.qty <= 0:
                    self.items.remove(st)
        return removed

    def count(self, item_id: str) -> int:
        return sum(st.qty for st in self.items if st.item_id == item_id)

    # -- trophies -------------------------------------------------------------
    def collect_boss(self, boss_id: str, name: str) -> None:
        """Defeating a boss adds it to the collection (trophy room)."""
        if boss_id not in self.collected_bosses:
            self.collected_bosses.append(boss_id)
            self.add_item(boss_id, 1, {boss_id: {"name": name,
                                                 "kind": "trophy"}})

    # -- money ------------------------------------------------------------------
    def add_gold(self, amount: int) -> None:
        self.gold = max(0, self.gold + amount)

    def spend(self, amount: int) -> bool:
        """Try to spend gold; True on success."""
        if self.gold >= amount:
            self.gold -= amount
            return True
        return False

    def to_json(self) -> dict:
        return {"gold": self.gold,
                "equipped": self.equipped,
                "weapons": {wid: {"level": w.level}
                            for wid, w in self.weapons.items()},
                "items": [st.to_json() for st in self.items],
                "trophies": list(self.collected_bosses)}

    def load_from(self, d: dict, defs: dict, weapon_defs: dict) -> None:
        """Restore from a save payload."""
        self.gold = int(d.get("gold", 0))
        for wid, wd in d.get("weapons", {}).items():
            w = self.add_or_get_weapon(wid, weapon_defs.get(
                wid, {"name": wid, "damage": 5}))
            w.level = int(wd.get("level", 1))
        self.equipped = d.get("equipped")
        self.items = [ItemStack.from_json(x, defs)
                      for x in d.get("items", [])]
        self.collected_bosses = list(d.get("trophies", []))


class Chest:
    """A storage chest: the same slots/tooltips UI as the player inventory."""

    def __init__(self, cid: str, items: list[ItemStack] | None = None) -> None:
        self.id = cid
        self.items = items or []

    def to_json(self) -> list[dict]:
        return [st.to_json() for st in self.items]

    @classmethod
    def from_json(cls, cid: str, d: list, defs: dict) -> "Chest":
        return cls(cid, [ItemStack.from_json(x, defs) for x in d])


def transfer(stack_src: "list[ItemStack]", stack_dst: "list[ItemStack]",
             idx: int, defs: dict, qty: int = 1) -> None:
    """Move qty from src list slot idx into dst (chest <-> player)."""
    if idx < 0 or idx >= len(stack_src):
        return
    st = stack_src[idx]
    move = min(qty, st.qty)
    # merge into an existing dst stack first
    for d in stack_dst:
        if d.item_id == st.item_id:
            d.add(move)
            break
    else:
        dd = defs.get(st.item_id, {})
        stack_dst.append(ItemStack(st.item_id, st.name, st.kind, move,
                                   dd.get("sprite", st.sprite)))
    st.take(move)
    if st.qty <= 0:
        stack_src.remove(st)
