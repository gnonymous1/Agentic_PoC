
from pydantic import BaseModel, Field

MASTER_BANNED_PHRASES: list[str] = [
    "delve", "testament to", "in conclusion", "revolutionizing",
    "moreover", "furthermore", "groundbreaking", "game-changer",
    "cutting-edge", "leverage", "synergy", "paradigm shift",
    "utilize", "optimize", "streamline", "innovative",
    "in today's", "in the ever-evolving", "it is important to note",
]


class FluffConfig(BaseModel):
    banned_phrases: list[str] = Field(default_factory=lambda: MASTER_BANNED_PHRASES[:])
    fluff_threshold: int = 3
    client_fluff_overrides: dict[str, list[str]] = Field(default_factory=dict)

    def get_effective_banned(self, client_id: str | None = None) -> list[str]:
        if client_id and client_id in self.client_fluff_overrides:
            return self.client_fluff_overrides[client_id]
        return self.banned_phrases

    def to_generator_rule(self, client_id: str | None = None) -> str:
        words = self.get_effective_banned(client_id)
        return f"NEVER use these fluff words: {', '.join(words)}."

    def to_critic_rule(self, client_id: str | None = None) -> str:
        words = self.get_effective_banned(client_id)
        return (
            f"any occurrence of these banned phrases counts as a defect: "
            f"{', '.join(words)}."
        )

    def to_validator(self, client_id: str | None = None) -> list[str]:
        return self.get_effective_banned(client_id)


fluff_config = FluffConfig()
