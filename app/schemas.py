from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ContentRequest(BaseModel):
    topic: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Raw topic seed or news snippet to manufacture content around.",
    )
    brand_voice_override: str | None = Field(
        None,
        max_length=1000,
        description="Optional brand voice instructions to inject into generation prompts.",
    )
    target_platforms: list[str] = Field(
        default=["twitter", "linkedin", "facebook", "blogspot"],
        description="Subset of platforms to generate content for.",
    )


class ContentResponse(BaseModel):
    request_id: str
    topic: str
    unified_truth_document: str
    prompt_hashes: dict = Field(default_factory=dict)
    utd_summary: str | None = None
    generated_content: dict
    critic_approved: bool
    refinement_cycles: int
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def compute_utd_summary(self):
        if self.utd_summary is None and self.unified_truth_document:
            self.utd_summary = self.unified_truth_document[:500]
        return self


class HealthResponse(BaseModel):
    status: str = "operational"
    service: str = "GNONE Content Manufacturing Loop"
