import pytest
from pydantic import ValidationError

from app.models.content_models import (
    BlogspotPost,
    FacebookPost,
    LinkedInPost,
    MultiPlatformContent,
    TwitterThread,
)


class TestTwitterThread:
    def test_valid_thread(self, sample_twitter_thread):
        assert len(sample_twitter_thread.posts) == 7
        assert all(len(p) <= 240 for p in sample_twitter_thread.posts)

    def test_too_few_posts(self):
        with pytest.raises(ValidationError):
            TwitterThread(posts=["Only one post"])

    def test_post_exceeds_max_chars(self):
        with pytest.raises(ValidationError):
            TwitterThread(posts=["A" * 241] * 5)

    def test_empty_post(self):
        with pytest.raises(ValidationError):
            TwitterThread(posts=["Valid post", "", "Valid post", "Valid post", "Valid post"])


class TestLinkedInPost:
    def test_valid_post(self, sample_linkedin_post):
        assert len(sample_linkedin_post.body) > 50
        assert len(sample_linkedin_post.hashtags) <= 10

    def test_too_many_hashtags(self):
        with pytest.raises(ValidationError):
            LinkedInPost(body="Valid body", hashtags=[f"#Tag{i}" for i in range(11)])


class TestFacebookPost:
    def test_valid_post(self, sample_facebook_post):
        assert sample_facebook_post.call_to_action


class TestBlogspotPost:
    def test_valid_post(self, sample_blogspot_post):
        assert len(sample_blogspot_post.title) <= 120
        assert len(sample_blogspot_post.meta_description) <= 320

    def test_title_too_long(self):
        with pytest.raises(ValidationError):
            BlogspotPost(
                title="A" * 121,
                seo_slug="test",
                meta_description="Valid description",
                html_body="<p>Content</p>",
            )


class TestMultiPlatformContent:
    def test_valid_content(self, sample_multiplatform_content):
        assert sample_multiplatform_content.twitter
        assert sample_multiplatform_content.linkedin
        assert sample_multiplatform_content.facebook
        assert sample_multiplatform_content.blogspot

    def test_fluff_rejection(self):
        fluff_body = (
            "This is a testament to the groundbreaking synergy we've achieved. "
            "Moreover, the cutting-edge paradigm shift will revolutionize the industry. "
            "Delve into the details below."
        )
        _long_text = "Clean content. " * 400
        with pytest.raises(ValidationError, match="fluff"):
            MultiPlatformContent(
                twitter=TwitterThread(posts=["Post 1"] * 5 + ["Post 6"]),
                linkedin=LinkedInPost(body=fluff_body),
                facebook=FacebookPost(body="Clean post", call_to_action="CTA"),
                blogspot=BlogspotPost(
                    title="Clean Title",
                    seo_slug="clean-title",
                    meta_description="Clean description",
                    html_body=f"<p>{_long_text}</p>",
                ),
            )
