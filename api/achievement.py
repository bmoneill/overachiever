class Achievement:
    def __init__(
        self,
        platform_id: int,
        achievement_id: int,
        title_id: int,
        name: str,
        description: str,
        unlocked: bool,
    ):
        self.platform_id = platform_id
        self.achievement_id = achievement_id
        self.title_id = title_id
        self.name = name
        self.description = description
        self.unlocked = unlocked
