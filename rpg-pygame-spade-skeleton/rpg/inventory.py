"""Inventory: gold, items, weapons, defeated-boss collection."""

from __future__ import annotations

from .models import Item, Weapon


class Inventory:
    """Owns everything the player carries. Shared via GameState only."""

    def __init__(self) -> None:
        self.gold: int = 50
        self.items: list[Item] = []
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

    # -- items & collection --------------------------------------------------
    def add_item(self, item: Item) -> None:
        self.items.append(item)

    def collect_boss(self, boss_id: str, name: str) -> None:
        """Defeating a boss adds it to the collection (trophy room)."""
        if boss_id not in self.collected_bosses:
            self.collected_bosses.append(boss_id)
            self.add_item(Item(boss_id, name, kind="boss_trophy"))

    def add_gold(self, amount: int) -> None:
        self.gold = max(0, self.gold + amount)

    def spend(self, amount: int) -> bool:
        """Try to spend gold; True on success."""
        if self.gold >= amount:
            self.gold -= amount
            return True
        return False
