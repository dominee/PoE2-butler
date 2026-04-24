"""Golden tests: PoE2 item text (mock-ggg/samples/*.txt)."""

from __future__ import annotations

from pathlib import Path

from app.domain.item import Item, ItemProperty
from app.domain.item_text import format_item_text

SAMPLES = Path(__file__).resolve().parent.parent.parent / "mock-ggg" / "samples"


def _read_golden(name: str) -> str:
    return (SAMPLES / name).read_text(encoding="utf-8")


def test_belt_headhunter_golden() -> None:
    item = Item(
        id="belt-1",
        item_class="Belts",
        name="Headhunter",
        type_line="Heavy Belt",
        base_type="Heavy Belt",
        rarity="Unique",
        ilvl=82,
        requirements=[ItemProperty(name="Level", value="50")],
        implicit_mods=["26% increased Stun Threshold", "Has 3 Charm Slots"],
        explicit_mods=[
            "+53 to maximum Life",
            "+27 to Strength",
            "+21 to Dexterity",
            "When you kill a Rare monster, you gain its Modifiers for 60 seconds",
        ],
        flavour_text=""""A man's soul rules from a cavern of bone, learns and
judges through flesh-born windows. The heart is meat.
The head is where the Man is."
- Lavianga, Advisor to Kaom""",
        corrupted=True,
    )
    assert format_item_text(item) == _read_golden("belt.txt")


def test_charm_evergreen_golden() -> None:
    item = Item(
        id="charm-1",
        item_class="Charms",
        name="Evergreen Golden Charm of the Doctor",
        type_line="",
        base_type="Golden Charm",
        rarity="Magic",
        ilvl=79,
        properties=[
            ItemProperty(name="Lasts 1 Second", value=None),
            ItemProperty(name="Consumes 80 of 80 Charges on use", value=None),
            ItemProperty(name="Currently has 80 Charges", value=None),
            ItemProperty(
                name="15% increased Rarity of Items found",
                value=None,
            ),
        ],
        requirements=[ItemProperty(name="Level", value="60")],
        implicit_mods=["Used when you kill a Rare or Unique enemy"],
        explicit_mods=[
            "Recover 303 Life when Used",
            "27% Chance to gain a Charge when you kill an enemy",
        ],
        trailer_note="Used automatically when condition is met. Can only hold charges while in "
        "belt. Refill at Wells or by killing monsters.",
    )
    assert format_item_text(item) == _read_golden("charm.txt")
