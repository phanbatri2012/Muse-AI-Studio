from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pytest
from prompt_utils import normalize_text_to_video_prompt, serialize_scene_prompt
text_to_video = pytest.importorskip(
    "A_workflow_text_to_video",
    reason="legacy desktop text-to-video workflow is optional",
)


def _build_scene_prompt() -> dict:
    return {
        "scene_id": "1",
        "summary": "Thor lands on a shattered bridge as storm clouds spiral over the battlefield.",
        "visual_style": "Live-action cinematic realism with grounded textures, dramatic weather, and feature-film lighting.",
        "character_lock": {
            "thor": {
                "name": "Thor",
                "reference_images": ["/tmp/thor_reference.png"],
            }
        },
        "action": {
            "primary_action": "Thor slams Mjolnir into the bridge and sends sparks across the stone.",
            "secondary_motion": "Dust whips around him while fragments slide toward the edge.",
        },
        "camera": {
            "framing": "wide hero shot",
            "angle": "low angle",
            "movement": "slow push-in",
            "focus": "Thor",
            "lens": "50mm anamorphic",
        },
        "lighting": {
            "setup": "Storm flashes and cold rim light shape the armor and broken bridge.",
            "time_of_day": "twilight",
            "mood": "tense and mythic",
        },
        "dialogue": [],
        "constraints": {
            "negative_prompt": ["cartoon", "low quality", "watermark"],
            "consistency_rules": ["Keep Thor's armor and silhouette consistent."],
            "safety_notes": [],
        },
    }


class PromptNormalizationHelperTests(unittest.TestCase):
    def test_normalize_text_to_video_prompt_converts_serialized_scene_json(self) -> None:
        serialized = serialize_scene_prompt(_build_scene_prompt())

        prompt = normalize_text_to_video_prompt(serialized)

        self.assertFalse(prompt.lstrip().startswith("{"))
        self.assertNotIn('"schema_version"', prompt)
        self.assertIn("Thor lands on a shattered bridge", prompt)
        self.assertIn("Camera:", prompt)
        self.assertNotIn("/tmp/thor_reference.png", prompt)

    def test_normalize_text_to_video_prompt_uses_prompt_v3_shot_plan(self) -> None:
        scene_prompt = _build_scene_prompt()

        prompt = normalize_text_to_video_prompt(
            "",
            prompt_v3={
                "creative_brief": {"style": "Realistic"},
                "shot_plan": scene_prompt,
            },
        )

        self.assertFalse(prompt.lstrip().startswith("{"))
        self.assertIn("Style:", prompt)
        self.assertIn("Avoid:", prompt)


class TextToVideoWorkflowPromptNormalizationTests(unittest.TestCase):
    def test_build_prompt_list_preserves_structured_json_prompts(self) -> None:
        workflow = text_to_video.TextToVideoWorkflow(
            project_name="demo_project",
            project_data={"_use_project_prompts": True},
        )
        serialized = serialize_scene_prompt(_build_scene_prompt())

        prompts = workflow._build_prompt_list([{"id": "1", "prompt": serialized}])

        self.assertEqual(len(prompts), 1)
        self.assertEqual(str(prompts[0].get("prompt") or ""), serialized)

    def test_prepare_prompt_text_for_submit_normalizes_structured_json_prompts(self) -> None:
        workflow = text_to_video.TextToVideoWorkflow(
            project_name="demo_project",
            project_data={"_use_project_prompts": True},
        )
        serialized = serialize_scene_prompt(_build_scene_prompt())

        prompt_text, valid = workflow._prepare_prompt_text_for_submit(
            serialized, prompt_id="1", scene_id="scene-1"
        )

        self.assertTrue(valid)
        self.assertFalse(prompt_text.lstrip().startswith("{"))
        self.assertIn("Action:", prompt_text)

    def test_get_prompt_text_preserves_prompt_loaded_from_test_json(self) -> None:
        tmpdir = tempfile.TemporaryDirectory(prefix="codex_test_workflow_prompt_norm_")
        self.addCleanup(tmpdir.cleanup)
        original_workflows_dir = text_to_video.WORKFLOWS_DIR
        text_to_video.WORKFLOWS_DIR = Path(tmpdir.name)
        self.addCleanup(lambda: setattr(text_to_video, "WORKFLOWS_DIR", original_workflows_dir))

        project_dir = Path(tmpdir.name) / "demo_project"
        project_dir.mkdir(parents=True, exist_ok=True)
        serialized = serialize_scene_prompt(_build_scene_prompt())
        (project_dir / "test.json").write_text(
            json.dumps({"prompts": {"text_to_video": [{"id": "1", "prompt": serialized}]}}),
            encoding="utf-8",
        )

        workflow = text_to_video.TextToVideoWorkflow(project_name="demo_project", project_data={})
        prompt_text = workflow._get_prompt_text("1")

        self.assertEqual(prompt_text, serialized)


if __name__ == "__main__":
    unittest.main()
