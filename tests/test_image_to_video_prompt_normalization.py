from __future__ import annotations

import unittest
import pytest
from prompt_utils import normalize_text_to_video_prompt
image_to_video = pytest.importorskip(
    "A_workflow_image_to_video",
    reason="legacy desktop image-to-video workflow is optional",
)


def _production_json_prompt() -> str:
    return (
        '{"production_id":"The_Last_Spark","description":"Smog rolls slowly through massive rusted metal mountains.",'
        '"audio":{"voice_over":{"narration_text":"Dense toxic air hangs over the valley."},'
        '"specific_sound_effects":[{"sfx_description":"massive concussive shockwave boom"},{"sfx_description":"fog blowing away violently"}]},'
        '"rendering_parameters":{"resolution":"4K","aspect_ratio":"16:9","motion":"high","camera_motion":"Epic wide"},'
        '"negative_prompt":"smile, cartoon, anime, watermark"}'
    )


class GenericPromptNormalizationTests(unittest.TestCase):
    def test_normalize_text_to_video_prompt_converts_generic_production_json(self) -> None:
        prompt = normalize_text_to_video_prompt(_production_json_prompt())

        self.assertFalse(prompt.lstrip().startswith("{"))
        self.assertIn("Smog rolls slowly through massive rusted metal mountains", prompt)
        self.assertIn("Sound design:", prompt)
        self.assertIn("Render:", prompt)
        self.assertIn("Avoid:", prompt)


class ImageToVideoWorkflowPromptTests(unittest.TestCase):
    def test_build_image_prompt_list_preserves_generic_json_prompt(self) -> None:
        workflow = image_to_video.ImageToVideoWorkflow(
            project_name="demo_project",
            project_data={"_use_project_prompts": True, "i2v_mode": "single"},
        )

        prompts = workflow._build_image_prompt_list(
            [{"id": "1", "prompt": f"  {_production_json_prompt()}  ", "image_link": "/tmp/sample.jpg"}]
        )

        self.assertEqual(len(prompts), 1)
        prompt_text = str(prompts[0].get("prompt") or "")
        self.assertEqual(prompt_text, f"  {_production_json_prompt()}  ")

    def test_build_image_prompt_list_preserves_blank_prompt_for_validation(self) -> None:
        workflow = image_to_video.ImageToVideoWorkflow(
            project_name="demo_project",
            project_data={"_use_project_prompts": True, "i2v_mode": "single", "idea": "fallback idea"},
        )

        prompts = workflow._build_image_prompt_list(
            [{"id": "1", "prompt": "   ", "image_link": "/tmp/sample.jpg"}]
        )

        self.assertEqual(len(prompts), 1)
        self.assertEqual(str(prompts[0].get("prompt") or ""), "   ")

    def test_prepare_prompt_text_for_submit_preserves_generic_json_prompt(self) -> None:
        workflow = image_to_video.ImageToVideoWorkflow(
            project_name="demo_project",
            project_data={"_use_project_prompts": True, "i2v_mode": "single"},
        )

        prompt_text, valid = workflow._prepare_prompt_text_for_submit(_production_json_prompt(), prompt_id="1")

        self.assertTrue(valid)
        self.assertEqual(prompt_text, _production_json_prompt())

    def test_prepare_prompt_text_for_submit_preserves_minimal_json_prompt(self) -> None:
        workflow = image_to_video.ImageToVideoWorkflow(
            project_name="demo_project",
            project_data={"_use_project_prompts": True, "i2v_mode": "single"},
        )

        prompt_text, valid = workflow._prepare_prompt_text_for_submit('{"production_id":"only_id"}', prompt_id="1")

        self.assertTrue(valid)
        self.assertEqual(prompt_text, '{"production_id":"only_id"}')

    def test_prepare_prompt_text_for_submit_rejects_empty_prompt(self) -> None:
        workflow = image_to_video.ImageToVideoWorkflow(
            project_name="demo_project",
            project_data={"_use_project_prompts": True, "i2v_mode": "single"},
        )

        prompt_text, valid = workflow._prepare_prompt_text_for_submit("   ", prompt_id="1")

        self.assertFalse(valid)
        self.assertEqual(prompt_text, "   ")


if __name__ == "__main__":
    unittest.main()
