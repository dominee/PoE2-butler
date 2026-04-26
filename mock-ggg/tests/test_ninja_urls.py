from app.ninja_urls import NinjaCharacterRef, parse_character_url
from app.poe_ninja import account_slug_to_user_id


def test_parse_profile_url() -> None:
    ref = parse_character_url(
        "https://poe.ninja/poe2/profile/dominee-9275/vaal/character/IamGothmog"
    )
    assert ref == NinjaCharacterRef("dominee-9275", "vaal", "IamGothmog")


def test_parse_builds_url() -> None:
    ref = parse_character_url("https://poe.ninja/poe2/builds/vaal/character/Ithax-6772/Wthax")
    assert ref == NinjaCharacterRef("Ithax-6772", "vaal", "Wthax")


def test_account_slug_to_user_id() -> None:
    assert account_slug_to_user_id("dominee-9275") == "dominee_9275"
    assert account_slug_to_user_id("Ithax-6772") == "Ithax_6772"
