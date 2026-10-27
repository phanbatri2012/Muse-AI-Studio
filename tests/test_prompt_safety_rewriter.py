from __future__ import annotations

import unittest

from prompt_utils import serialize_scene_prompt
from prompt_safety_rewriter import rewrite_prompt_for_content_filter, rewrite_reference_prompt_for_content_filter
from workflow_error_policy import build_error_guidance


def _build_scene_prompt() -> dict:
    return {
        "scene_id": "1",
        "summary": "Hulk charges through the ruins while Thor drops from the storm clouds above him.",
        "visual_style": "Live-action cinematic realism with mythic storm lighting.",
        "action": {
            "primary_action": "Thor swings Mjolnir toward Hulk as debris erupts around them.",
            "secondary_motion": "Hulk tears up broken concrete and lunges forward.",
        },
        "camera": {
            "framing": "wide action shot",
            "angle": "low angle",
            "movement": "fast push-in",
        },
        "lighting": {
            "setup": "Cold storm flashes with harsh rim light.",
            "time_of_day": "twilight",
            "mood": "intense",
        },
        "dialogue": [],
        "constraints": {
            "negative_prompt": ["Hulk face close-up", "Thor logo"],
            "consistency_rules": [],
            "safety_notes": [],
        },
    }


class PromptSafetyRewriterTests(unittest.TestCase):
    def test_rewrite_prompt_for_content_filter_preserves_json_but_rewrites_ip_names(self) -> None:
        serialized = serialize_scene_prompt(_build_scene_prompt())

        rewritten, changed = rewrite_prompt_for_content_filter(serialized)

        self.assertTrue(changed)
        self.assertTrue(rewritten.lstrip().startswith("{"))
        self.assertNotIn("Hulk", rewritten)
        self.assertNotIn("Thor", rewritten)
        self.assertNotIn("Mjolnir", rewritten)
        self.assertIn("gamma-powered giant", rewritten)
        self.assertIn("storm-wielding armored warrior", rewritten)
        self.assertIn("rune-etched war hammer", rewritten)

    def test_rewrite_prompt_for_content_filter_rewrites_plain_text_ip_names(self) -> None:
        rewritten, changed = rewrite_prompt_for_content_filter("Hulk and Thor clash as Mjolnir cracks the street.")

        self.assertTrue(changed)
        self.assertNotIn("Hulk", rewritten)
        self.assertNotIn("Thor", rewritten)
        self.assertNotIn("Mjolnir", rewritten)
        self.assertIn("gamma-powered giant", rewritten)
        self.assertIn("storm-wielding armored warrior", rewritten)

    def test_rewrite_reference_prompt_for_content_filter_anonymizes_aliases_but_keeps_prompt_usable(self) -> None:
        rewritten, changed = rewrite_reference_prompt_for_content_filter(
            "Character THRON_SIDE in full divine charge while GREN_3Q rushes in and THRON raises the hammer.",
            reference_aliases=["THRON_SIDE", "THRON_3Q", "GREN_3Q"],
        )

        self.assertTrue(changed)
        self.assertNotIn("THRON_SIDE", rewritten)
        self.assertNotIn("THRON", rewritten)
        self.assertNotIn("GREN_3Q", rewritten)
        self.assertNotIn("hammer", rewritten.lower())
        self.assertNotIn("divine", rewritten.lower())
        self.assertIn("reference subject A", rewritten)
        self.assertIn("reference subject B", rewritten)
        self.assertIn("charged weapon", rewritten)

    def test_build_error_guidance_mentions_ip_policy_for_public_error_ip_input_image(self) -> None:
        guidance = build_error_guidance("3", "PUBLIC_ERROR_IP_INPUT_IMAGE")

        self.assertIn("IP", guidance.upper())
        self.assertIn("generic", guidance.lower())

    def test_build_error_guidance_mentions_prominent_people_policy(self) -> None:
        guidance = build_error_guidance("400", "Request contains an invalid argument. [PUBLIC_ERROR_PROMINENT_PEOPLE_FILTER_FAILED]")

        self.assertIn("franchise", guidance.lower())
        self.assertIn("generic", guidance.lower())


if __name__ == "__main__":
    unittest.main()
