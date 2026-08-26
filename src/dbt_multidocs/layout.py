"""Lane ordering, colours and labels for the project swimlanes."""
from __future__ import annotations

import re
from typing import List, Optional, Sequence

# Ordered layer patterns, first match wins. Deliberately broader than the
# reference script's raw/int/mart/dashboard so that other naming schemes
# (staging -> core -> analytics, for one) also lay out top to bottom.
DEFAULT_LAYERS: Sequence[str] = (
    r"raw|seed|landing|source",
    r"staging|stg",
    r"core|int|intermediate|conform",
    r"mart|warehouse|dim|fact",
    r"analytic|dashboard|report|bi|expos|serving",
)

UNRANKED = 90

# 12 hues, distinguishable in both themes.
PALETTE: Sequence[str] = (
    "#60a5fa", "#34d399", "#fbbf24", "#a78bfa",
    "#f472b6", "#22d3ee", "#fb923c", "#f87171",
    "#94a3b8", "#4ade80", "#c084fc", "#facc15",
)


def layer_rank(name: str, layers: Optional[Sequence[str]] = None) -> int:
    for i, pattern in enumerate(layers or DEFAULT_LAYERS):
        try:
            if re.search(pattern, name, re.I):
                return i
        except re.error:
            if pattern.lower() in name.lower():
                return i
    return UNRANKED


def pretty(name: str) -> str:
    """proj_marts_finance -> marts / finance ; dbt_staging -> staging"""
    s = re.sub(r"^(proj|project|dbt)[_-]", "", name) or name
    return s.replace("_", " · ").replace("-", " · ")


def color_for(index: int) -> str:
    return PALETTE[index % len(PALETTE)]


def order_projects(ids: List[str], layers: Optional[Sequence[str]] = None) -> List[str]:
    return sorted(ids, key=lambda p: (layer_rank(p, layers), p))
