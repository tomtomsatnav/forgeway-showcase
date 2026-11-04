"""Print WCAG 2.x contrast ratios for each theme palette (see DESIGN.md)."""

from __future__ import annotations

PALETTES: dict[str, dict[str, str]] = {
    "pro-light": {
        "base": "#F6F4EF",
        "raised": "#FFFFFF",
        "sunken": "#EDEAE3",
        "text": "#1B1C1A",
        "muted": "#5E605A",
        "accent": "#1D5C4B",
        "on-accent": "#FFFFFF",
        "success": "#2F6B3A",
        "danger": "#A3352B",
        "border": "#84867E",
        "tier-capstone": "#1F4F86",
    },
    "pro-dark": {
        "base": "#131513",
        "raised": "#1C1F1C",
        "sunken": "#0E100E",
        "text": "#E9E6DE",
        "muted": "#A3A59C",
        "accent": "#6FC2A6",
        "on-accent": "#0E1B16",
        "success": "#8FD19B",
        "danger": "#F08A7E",
        "border": "#70736B",
        "tier-capstone": "#8FBDF0",
    },
    "rpg-light": {
        "base": "#EFE4CB",
        "raised": "#F7EFDC",
        "sunken": "#E5D7B8",
        "text": "#2A1F14",
        "muted": "#6B5A44",
        "accent": "#8E2A21",
        "on-accent": "#FBF3E2",
        "success": "#386429",
        "danger": "#8E2A21",
        "border": "#897453",
        "tier-capstone": "#2F4A7C",
    },
    "rpg-dark": {
        "base": "#0E1615",
        "raised": "#16211F",
        "sunken": "#0A1110",
        "text": "#EDE3CC",
        "muted": "#B3A88F",
        "accent": "#D9A546",
        "on-accent": "#1A1206",
        "success": "#9CCB7E",
        "danger": "#EE8366",
        "border": "#766C57",
        "tier-capstone": "#9DB9EE",
    },
}


# Tokens only the atlas's islands need: their names, the hatch's line and the hover tint.
ISLANDS: dict[str, dict[str, str]] = {
    "pro-light": {"secondary": "#3D3F3B", "subtle": "#D5D2C8", "accent-soft": "#DCE8E2"},
    "pro-dark": {"secondary": "#C9C6BD", "subtle": "#2E312D", "accent-soft": "#1B2B25"},
    "rpg-light": {"secondary": "#43331F", "subtle": "#CDBB95", "accent-soft": "#E9D2B8"},
    "rpg-dark": {"secondary": "#D3C8AE", "subtle": "#26332F", "accent-soft": "#2A2514"},
}


def _channel(value: float) -> float:
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    digits = hex_colour.lstrip("#")
    r, g, b = (_channel(int(digits[i : i + 2], 16) / 255) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def mix(top: str, under: str, opacity: float) -> str:
    """`top` at `opacity` over `under`, as an opaque colour."""
    a, b = top.lstrip("#"), under.lstrip("#")
    return "#" + "".join(
        f"{round(int(a[i : i + 2], 16) * opacity + int(b[i : i + 2], 16) * (1 - opacity)):02X}"
        for i in (0, 2, 4)
    )


def zone_grounds(p: dict[str, str], island: dict[str, str]) -> list[str]:
    """What a selected zone's faintest text can sit on (Atlas.tsx, text-muted): the island under
    a hatch line at 0.5, with or without the fog's thinnest layer (the base at 0.4), or a hovered
    waypoint's opaque tint."""
    hatched = mix(island["subtle"], p["raised"], 0.5)
    return [hatched, mix(p["base"], hatched, 0.4), island["accent-soft"]]


def world_grounds(p: dict[str, str], island: dict[str, str]) -> list[str]:
    """What a locked island's name can sit on (WorldMap.tsx, text-secondary): as above, and the
    hover tint under the hatch and fog, not over them."""
    hatched = [mix(island["subtle"], c, 0.5) for c in (p["raised"], island["accent-soft"])]
    return [*hatched, *(mix(p["base"], c, 0.4) for c in hatched)]


if __name__ == "__main__":
    for name, p in PALETTES.items():
        pairs = {k: contrast(p[k], p["base"]) for k in ("text", "muted", "accent", "success",
                                                         "danger", "border")}  # fmt: skip
        pairs["capstone/worst-surface"] = min(
            contrast(p["tier-capstone"], p[surface]) for surface in ("base", "raised", "sunken")
        )
        if pairs["capstone/worst-surface"] < 4.5:
            raise SystemExit(f"{name}: tier-capstone is below 4.5:1")
        pairs["on-accent/accent"] = contrast(p["on-accent"], p["accent"])
        pairs["border/worst-surface"] = min(
            contrast(p["border"], p[surface]) for surface in ("base", "raised", "sunken")
        )
        pairs["zone-text/worst-ground"] = min(
            contrast(p["muted"], ground) for ground in zone_grounds(p, ISLANDS[name])
        )
        pairs["island-name/worst-ground"] = min(
            contrast(ISLANDS[name]["secondary"], ground)
            for ground in world_grounds(p, ISLANDS[name])
        )
        if min(pairs["zone-text/worst-ground"], pairs["island-name/worst-ground"]) < 4.5:
            raise SystemExit(f"{name}: text on an atlas island is below 4.5:1")
        print(f"{name:10}", "  ".join(f"{k} {v:.1f}" for k, v in pairs.items()))
