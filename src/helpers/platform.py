PLATFORM_PSN = 0
PLATFORM_XBOX = 1
PLATFORM_STEAM = 2

PLATFORM_ID_MAP: dict[int, str] = {
    PLATFORM_PSN: "psn",
    PLATFORM_XBOX: "xbox",
    PLATFORM_STEAM: "steam",
}

PLATFORM_NAME_MAP: dict[str, int] = {
    "psn": PLATFORM_PSN,
    "xbox": PLATFORM_XBOX,
    "steam": PLATFORM_STEAM,
}

X360_MEDIA_TYPES = {
    "Xbox360Game",
    "XboxArcadeGame"
}
