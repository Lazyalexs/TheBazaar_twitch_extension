from __future__ import annotations

import re
from dataclasses import dataclass

from .log_companion import PURCHASE_RE, STATE_RE


SOLD_RE = re.compile(r"Sold Card (\S+) for (\d+) gold")
COMBAT_START_RE = re.compile(r"State changed from \[[^\]]+\] to \[(PVPCombatState|CombatState)\]")
CARDS_DEALT_RE = re.compile(r"Cards Dealt: (.*)")


@dataclass(frozen=True)
class LogStats:
    phase: str
    purchases: int
    sales: int
    sold_gold: int
    combats: int
    pvp_combats: int
    combat_completions: int
    cards_dealt_events: int
    last_state: str | None


def phase_from_state(state: str | None) -> str:
    if state is None:
        return "unknown"
    if "CombatState" in state:
        return "combat"
    if state in {"ChoiceState", "EncounterState", "ReplayState", "LevelUpState"}:
        return "shopping"
    if state in {"MainMenuState", "HomeState"}:
        return "menu"
    if "EndRun" in state:
        return "game_over"
    return state


def summarize_log_text(log_text: str) -> LogStats:
    purchases = 0
    sales = 0
    sold_gold = 0
    combats = 0
    pvp_combats = 0
    combat_completions = 0
    cards_dealt_events = 0
    last_state: str | None = None

    for line in log_text.splitlines():
        state_match = STATE_RE.search(line)
        if state_match:
            last_state = state_match.group(1)

        purchase_match = PURCHASE_RE.search(line)
        if purchase_match and purchase_match.group(3).startswith("Player"):
            purchases += 1

        sold_match = SOLD_RE.search(line)
        if sold_match:
            sales += 1
            sold_gold += int(sold_match.group(2))

        combat_match = COMBAT_START_RE.search(line)
        if combat_match:
            combats += 1
            if combat_match.group(1) == "PVPCombatState":
                pvp_combats += 1

        if "Combat simulation completed" in line:
            combat_completions += 1

        if CARDS_DEALT_RE.search(line):
            cards_dealt_events += 1

    return LogStats(
        phase=phase_from_state(last_state),
        purchases=purchases,
        sales=sales,
        sold_gold=sold_gold,
        combats=combats,
        pvp_combats=pvp_combats,
        combat_completions=combat_completions,
        cards_dealt_events=cards_dealt_events,
        last_state=last_state,
    )
