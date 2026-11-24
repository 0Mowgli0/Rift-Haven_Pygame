"""Entities: Player, Mob, Boss, Weapon, Item.

Pure data holders + tiny helpers. No pygame drawing and no agent code here:
rendering lives in ui.py, agent logic in rpg/agents/.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class Stats:
    """Upgradable player stats."""
    hp: int = 100
    max_hp: int = 100
    attack: int = 10
    defense: int = 2
    speed: int = 160  # px/s
    shown_hp: float = -1.0  # lerped value for smooth HP bar animation

    def upgrade(self, stat: str, amount: int = 10) -> None:
        """Increment one stat by `amount`."""
        if stat == "hp":
            self.max_hp += amount
            self.hp = self.max_hp
        elif hasattr(self, stat):
            setattr(self, stat, getattr(self, stat) + amount)


@dataclass
class Weapon:
    id: str
    name: str
    damage: int
    level: int = 1
    cost_per_level: int = 20
    unlocked: bool = True

    def upgrade_cost(self) -> int:
        return self.cost_per_level * self.level

    def total_damage(self, player_attack: int) -> int:
        return self.damage * self.level + player_attack


@dataclass
class Item:
    id: str
    name: str
    kind: str = "misc"  # "misc" | "boss_trophy" | "weapon_drop"
    value: int = 0


@dataclass
class Mob:
    """A small enemy. AI ticks come from the EnemyAgent (or local director)."""
    id: str
    kind: str
    name: str
    x: float
    y: float
    hp: int
    max_hp: int
    attack: int
    defense: int
    speed: float
    gold: int
    color: tuple[int, int, int]
    vx: float = 0.0
    vy: float = 0.0
    flash: float = 0.0          # seconds of white hit-flash left
    shown_hp: float = -1.0      # lerped value for smooth HP bar animation
    behavior: str = "melee"     # charger | swoop | caster | melee (enemies.json)
    ranged: dict = field(default_factory=dict)  # caster config (imp fireball)
    tel: float = 0.0            # attack windup / charge telegraph, seconds
    charge: float = 0.0         # remaining charge-sprint time
    atk_cd: float = 0.0         # contact-cast attack cooldown

    @property
    def alive(self) -> bool:
        return self.hp > 0


@dataclass
class Boss(Mob):
    """A boss; may drop a weapon and gains attack phases (data/bosses.json)."""
    weapon: str | None = None
    phases: list[dict] = field(default_factory=list)  # {"at", "line", "attacks"}
    phase_idx: int = 0
    tel_name: str = ""          # attack being telegraphed ("slam"/"burst")
    tel_radius: float = 0.0
    intro: str = ""             # spoken line at fight start

    def cd_mult(self) -> float:
        """Attack-interval multiplier for the current phase."""
        if not self.phases:
            return 1.0
        i = min(self.phase_idx, len(self.phases) - 1)
        return self.phases[i].get("cooldown_mult", 1.0)

    def attack_list(self) -> list[str]:
        """Attacks available in the current phase."""
        if not self.phases:
            return ["slam"]
        i = min(self.phase_idx, len(self.phases) - 1)
        return self.phases[i].get("attacks", ["slam"])

    @classmethod
    def from_data(cls, bid: str, data: dict, x: float, y: float) -> "Boss":
        return cls(
            id=bid, kind=bid, name=data["name"], x=x, y=y,
            hp=data["hp"], max_hp=data["hp"],
            attack=data["attack"], defense=data["defense"],
            speed=data["speed"], gold=data["gold"],
            color=tuple(data.get("color", (255, 80, 80))),
            weapon=data.get("weapon"),
            phases=data.get("phases", []),
            intro=data.get("dialogue", ""),
        )


@dataclass
class Player:
    """Player avatar owned by the pygame loop; agent side mirrors key facts."""
    x: float
    y: float
    stats: Stats = field(default_factory=Stats)
    facing: int = 0  # 0 down, 1 up, 2 left, 3 right
    flash: float = 0.0  # white hit-flash after taking damage


def make_mob(mid: int, kind: str, data: dict, x: float, y: float) -> Mob:
    """Build a Mob from a data/enemies.json entry with a little jitter."""
    return Mob(
        id=f"{kind}_{mid}", kind=kind, name=data["name"],
        x=x + random.randint(-16, 16), y=y + random.randint(-16, 16),
        hp=data["hp"], max_hp=data["hp"],
        attack=data["attack"], defense=data["defense"],
        speed=data["speed"], gold=data["gold"],
        color=tuple(data.get("color", (200, 200, 80))),
        behavior=data.get("behavior", "melee"),
        ranged=data.get("ranged", {}),
    )
