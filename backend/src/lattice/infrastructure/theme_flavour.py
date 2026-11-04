"""Optional per-theme flavour text (zone names, quest titles, lore), keyed by domain ids.

Flavour is presentation only. It is validated against the catalogue so a renamed exercise
cannot silently lose its title, but nothing in grading or progression reads it.
"""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from lattice.domain.content import ContentError, PrerequisiteGraph, Tier
from lattice.infrastructure.yaml_loading import load_yaml


class BranchFlavour(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    epithet: str
    lore: str


class PathFlavour(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    epithet: str


class BossFlavour(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    epithet: str
    lore: str
    defeat: str  # shown when the capstone is passed


class ThemeFlavour(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    branches: dict[str, BranchFlavour] = {}
    paths: dict[str, PathFlavour] = {}
    quests: dict[str, str] = {}
    bosses: dict[str, BossFlavour] = {}  # keyed by capstone exercise id


def load_flavour(
    content_dir: Path,
    theme: str,
    graph: PrerequisiteGraph,
    path_ids: Collection[str] = (),
    *,
    require_bosses: bool = False,
) -> ThemeFlavour:
    """Load `content/themes/<theme>/flavour.yaml`, or an empty flavour if there is none.

    With `require_bosses`, every capstone exercise must have a boss (the shipped content is
    checked this way; small trees in tests need none).
    """
    path = content_dir / "themes" / theme / "flavour.yaml"
    if not path.is_file():
        return ThemeFlavour()
    try:
        data = load_yaml(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as err:
        raise ContentError([f"{path}: invalid YAML: {err}"]) from err
    flavour = ThemeFlavour.model_validate(data or {})
    problems = [
        f"{path}: unknown branch '{b}'" for b in flavour.branches if b not in graph.branches
    ] + [f"{path}: unknown exercise '{e}'" for e in flavour.quests if e not in graph.exercises]
    problems.extend(
        f"{path}: boss '{e}' is not a capstone exercise"
        for e in flavour.bosses
        if e not in graph.exercises or graph.exercises[e].tier is not Tier.CAPSTONE
    )
    problems.extend(f"{path}: unknown path '{p}'" for p in flavour.paths if p not in path_ids)
    if require_bosses:
        problems.extend(
            f"{path}: capstone '{e.id}' has no boss"
            for e in graph.exercises.values()
            if e.tier is Tier.CAPSTONE and e.id not in flavour.bosses
        )
    if problems:
        raise ContentError(problems)
    return flavour
