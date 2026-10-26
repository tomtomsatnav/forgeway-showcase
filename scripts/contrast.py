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


def _channel(value: float) -> float:
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    digits = hex_colour.lstrip("#")
    r, g, b = (_channel(int(digits[i : i + 2], 16) / 255) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


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
        print(f"{name:10}", "  ".join(f"{k} {v:.1f}" for k, v in pairs.items()))
