import re

from pydantic import BaseModel, Field, field_validator

from app.core.fluff_config import fluff_config

_FLUFF_PATTERN = re.compile(
    "|".join(re.escape(p) for p in fluff_config.banned_phrases),
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(html: str) -> str:
    return _HTML_TAG_RE.sub("", html)


class TwitterThread(BaseModel):
    posts: list[str] = Field(
        ...,
        description="High-impact thread of 5-10 posts, each max 240 characters.",
        min_length=5,
        max_length=10,
    )

    @field_validator("posts")
    @classmethod
    def validate_post_lengths(cls, v: list[str]) -> list[str]:
        for i, post in enumerate(v):
            stripped = post.strip()
            if len(stripped) > 240:
                raise ValueError(
                    f"Twitter post {i+1} exceeds 240 characters "
                    f"(got {len(stripped)})."
                )
            if not stripped:
                raise ValueError(f"Twitter post {i+1} is empty.")
        return v


class LinkedInPost(BaseModel):
    body: str = Field(
        ...,
        description="Professional executive-toned post with clean spacing and bullet points.",
    )
    hashtags: list[str] = Field(
        default_factory=list,
        description="Relevant industry hashtags for LinkedIn reach.",
        max_length=10,
    )


class FacebookPost(BaseModel):
    body: str = Field(
        ...,
        description="Conversational community-focused engagement post ending with a call-to-action.",
    )
    call_to_action: str = Field(
        ...,
        description="The explicit CTA appended to the post.",
    )


class BlogspotPost(BaseModel):
    title: str = Field(..., max_length=120)
    seo_slug: str = Field(..., max_length=200)
    meta_description: str = Field(..., max_length=320)
    html_body: str = Field(
        ...,
        description="Long-form SEO-optimized semantic HTML5 body using <h2>, <h3>, <strong> tags.",
    )

    @field_validator("html_body")
    @classmethod
    def validate_min_word_count(cls, v: str) -> str:
        text = _strip_html(v)
        word_count = len(text.split())
        if word_count < 600:
            raise ValueError(
                f"html_body must contain at least 600 words after stripping HTML "
                f"(got {word_count})."
            )
        return v


class MultiPlatformContent(BaseModel):
    twitter: TwitterThread
    linkedin: LinkedInPost
    facebook: FacebookPost
    blogspot: BlogspotPost

    @field_validator("twitter", "linkedin", "facebook", "blogspot")
    @classmethod
    def reject_ai_fluff(cls, v: BaseModel, info) -> BaseModel:
        if isinstance(v, str):
            text = v
        elif hasattr(v, "body") and isinstance(v.body, str):
            text = v.body
        elif hasattr(v, "html_body") and isinstance(v.html_body, str):
            text = v.html_body
        else:
            text = str(v)

        hits = _FLUFF_PATTERN.findall(text.lower())
        if len(hits) >= fluff_config.fluff_threshold:
            raise ValueError(
                f"Excessive AI fluff detected in {info.field_name}: "
                f"found {hits}. Re-run required."
            )
        return v
