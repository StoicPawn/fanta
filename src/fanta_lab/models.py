from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List

@dataclass
class LeagueRules:
    budget: int = 500
    managers: int = 8
    slots_gk: int = 3
    slots_def: int = 8
    slots_mid: int = 8
    slots_fwd: int = 6
    goal_gk: float = 3.0
    goal_def: float = 3.0
    goal_mid: float = 3.0
    goal_fwd: float = 3.0
    assist: float = 1.0
    clean_sheet_gk: float = 1.0
    clean_sheet_def: float = 0.0
    yellow: float = -0.5
    red: float = -1.0
    defense_modifier: bool = False
    defense_modifier_strength: float = 1.0
    base_vote_weight: float = 1.0

    def slots(self) -> Dict[str, int]:
        return {"P": self.slots_gk, "D": self.slots_def, "C": self.slots_mid, "A": self.slots_fwd}

    def to_dict(self):
        return asdict(self)

@dataclass
class AuctionPurchase:
    manager: str
    player: str
    role: str
    price: float
    fair_value_before: float | None = None

@dataclass
class DataQualityReport:
    expected_teams: int
    observed_teams: int
    player_count: int
    missing_teams: List[str] = field(default_factory=list)
    unmatched_players: List[str] = field(default_factory=list)
    stale_sources: List[str] = field(default_factory=list)
    source_counts: Dict[str, int] = field(default_factory=dict)

    @property
    def certified(self) -> bool:
        return self.observed_teams == self.expected_teams and not self.missing_teams and self.player_count >= 400
