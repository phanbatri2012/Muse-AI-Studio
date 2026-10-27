from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
	import A_workflow_image_to_video as image_to_video
except Exception as exc:  # pragma: no cover - environment-specific
	image_to_video = None
	_IMPORT_ERROR = str(exc)
else:
	_IMPORT_ERROR = ""


@unittest.skipIf(image_to_video is None, f"ImageToVideo workflow env unavailable: {_IMPORT_ERROR}")
class ImageToVideoRetryPolicyTests(unittest.TestCase):
	def _workflow(self):
		return image_to_video.ImageToVideoWorkflow(
			project_name="demo_project",
			project_data={"_use_project_prompts": True, "i2v_mode": "single"},
		)

	def test_retry_wait_seconds_scales_for_429(self) -> None:
		workflow = self._workflow()

		self.assertEqual(
			workflow._resolve_retry_wait_seconds("429", {"headers": {}}, 12, 1),
			12,
		)
		self.assertEqual(
			workflow._resolve_retry_wait_seconds("429", {"headers": {}}, 12, 2),
			24,
		)
		self.assertEqual(
			workflow._resolve_retry_wait_seconds("429", {"headers": {}}, 12, 3),
			36,
		)

	def test_retry_wait_seconds_prefers_retry_after_header(self) -> None:
		workflow = self._workflow()

		self.assertEqual(
			workflow._resolve_retry_wait_seconds("429", {"headers": {"Retry-After": "45"}}, 12, 1),
			45,
		)

	def test_resolve_backend_error_message_builds_429_fallback(self) -> None:
		workflow = self._workflow()

		self.assertIn(
			"429",
			workflow._resolve_backend_error_message("429", "", {"status": 429, "reason": "Too Many Requests"}),
		)

	def test_mark_remaining_prompts_failed_marks_each_remaining_prompt(self) -> None:
		workflow = self._workflow()
		calls = []

		def fake_mark(prompt_id, prompt_text, scene_ids, error_code, message):
			calls.append((prompt_id, prompt_text, len(scene_ids), error_code, message))

		workflow._mark_prompt_failed = fake_mark
		prompts = [
			{"id": "1", "prompt": "first"},
			{"id": "2", "prompt": "second"},
			{"id": "3", "prompt": "third"},
		]

		workflow._mark_remaining_prompts_failed(
			prompts,
			1,
			2,
			"429",
			"Resource has been exhausted (e.g. check quota).",
		)

		self.assertEqual(
			calls,
			[
				("2", "second", 2, "429", "Resource has been exhausted (e.g. check quota)."),
				("3", "third", 2, "429", "Resource has been exhausted (e.g. check quota)."),
			],
			)

	def test_success_status_without_video_url_marks_failed(self) -> None:
		workflow = self._workflow()
		scene_id = "scene-1"
		updates = []
		workflow._scene_status = {
			scene_id: {"status": "MEDIA_GENERATION_STATUS_ACTIVE", "operation_name": "op-1"}
		}
		workflow._scene_to_prompt = {scene_id: {"prompt_id": "1", "index": 0}}
		workflow._get_prompt_text = lambda prompt_id: "prompt"
		workflow._update_state_entry = lambda *args, **kwargs: updates.append((args, kwargs))

		ok = workflow._handle_status_response(json.dumps({
			"operations": [
				{
					"sceneId": scene_id,
					"status": "MEDIA_GENERATION_STATUS_SUCCESSFUL",
					"operation": {"metadata": {}},
				}
			]
		}))

		self.assertTrue(ok)
		self.assertEqual(updates[-1][0][4], "FAILED")
		self.assertEqual(updates[-1][1].get("error"), "NO_VIDEO_URL")

	def test_success_status_with_download_failure_marks_failed(self) -> None:
		workflow = self._workflow()
		scene_id = "scene-1"
		updates = []
		workflow._scene_status = {
			scene_id: {"status": "MEDIA_GENERATION_STATUS_ACTIVE", "operation_name": "op-1"}
		}
		workflow._scene_to_prompt = {scene_id: {"prompt_id": "1", "index": 0}}
		workflow._get_prompt_text = lambda prompt_id: "prompt"
		workflow._download_video = lambda url, prompt_idx: ""
		workflow._update_state_entry = lambda *args, **kwargs: updates.append((args, kwargs))

		ok = workflow._handle_status_response(json.dumps({
			"operations": [
				{
					"sceneId": scene_id,
					"status": "MEDIA_GENERATION_STATUS_SUCCESSFUL",
					"operation": {
						"metadata": {
							"video": {"fifeUrl": "https://example.test/video.mp4"}
						}
					},
				}
			]
		}))

		self.assertTrue(ok)
		self.assertEqual(updates[-1][0][4], "FAILED")
		self.assertEqual(updates[-1][1].get("error"), "DOWNLOAD_VIDEO")

	def test_workflows_status_response_maps_by_primary_media_id(self) -> None:
		workflow = self._workflow()
		scene_id = "scene-1"
		updates = []
		workflow._scene_status = {
			scene_id: {"status": "MEDIA_GENERATION_STATUS_ACTIVE", "operation_name": "primary-media-1"}
		}
		workflow._scene_to_prompt = {scene_id: {"prompt_id": "1", "index": 0}}
		workflow._get_prompt_text = lambda prompt_id: "prompt"
		workflow._download_video = lambda url, prompt_idx: "/tmp/generated.mp4"
		workflow._update_state_entry = lambda *args, **kwargs: updates.append((args, kwargs))

		ok = workflow._handle_status_response(json.dumps({
			"operations": [],
			"workflows": [
				{
					"name": "workflow-1",
					"done": True,
					"metadata": {
						"primaryMediaId": "primary-media-1",
						"video": {"fifeUrl": "https://example.test/video.mp4"},
					},
				}
			]
		}))

		self.assertTrue(ok)
		self.assertEqual(updates[-1][0][4], "SUCCESSFUL")
		self.assertEqual(updates[-1][1].get("video_url"), "https://example.test/video.mp4")
		self.assertEqual(updates[-1][1].get("video_path"), "/tmp/generated.mp4")

	def test_i2v_upload_cache_is_scoped_to_project_id(self) -> None:
		workflow = self._workflow()
		entry = {"media_id": "media-1", "cached_at": 9999999999, "project_id": "project-1"}

		self.assertTrue(workflow._i2v_cache_valid(entry, "/tmp/image.png", "project-1"))
		self.assertFalse(workflow._i2v_cache_valid(entry, "/tmp/image.png", "project-2"))
		self.assertFalse(workflow._i2v_cache_valid({"media_id": "media-1", "cached_at": 9999999999}, "/tmp/image.png", "project-1"))

	def test_switch_to_next_profile_after_quota_exhausted_updates_settings_and_config(self) -> None:
		workflow = self._workflow()
		with tempfile.TemporaryDirectory(prefix="codex_i2v_profiles_") as tmpdir:
			root = Path(tmpdir)
			(root / "PROFILE_1" / "Default").mkdir(parents=True, exist_ok=True)
			(root / "PROFILE_1" / "Default" / "Cookies").write_text("", encoding="utf-8")
			(root / "PROFILE_E2E_VEOANTI" / "Default").mkdir(parents=True, exist_ok=True)
			(root / "PROFILE_E2E_VEOANTI" / "Default" / "Preferences").write_text("{}", encoding="utf-8")
			(root / "PROFILE_2" / "Default").mkdir(parents=True, exist_ok=True)
			(root / "PROFILE_2" / "Default" / "Preferences").write_text("{}", encoding="utf-8")
			(root / "__codex_ignore__" / "Default").mkdir(parents=True, exist_ok=True)

			saved_settings = {}
			saved_config = {}
			original_root = image_to_video.CHROME_USER_DATA_ROOT
			original_load_settings = image_to_video.SettingsManager.load_settings
			original_save_settings = image_to_video.SettingsManager.save_settings
			original_load_config = image_to_video.SettingsManager.load_config
			original_save_config = image_to_video.SettingsManager.save_config
			try:
				image_to_video.CHROME_USER_DATA_ROOT = root
				image_to_video.SettingsManager.load_settings = staticmethod(lambda: {"current_profile": "PROFILE_1"})
				image_to_video.SettingsManager.save_settings = staticmethod(lambda data: saved_settings.update(data))
				image_to_video.SettingsManager.load_config = staticmethod(
					lambda: {
						"account1": {
							"folder_user_data_get_token": str(root / "PROFILE_1"),
							"URL_GEN_TOKEN": "https://labs.google/fx/vi/tools/flow/project/demo",
						}
					}
				)
				image_to_video.SettingsManager.save_config = staticmethod(lambda data: saved_config.update(data))

				switched, next_profile = workflow._switch_to_next_profile_after_quota_exhausted("PROFILE_1")
			finally:
				image_to_video.CHROME_USER_DATA_ROOT = original_root
				image_to_video.SettingsManager.load_settings = original_load_settings
				image_to_video.SettingsManager.save_settings = original_save_settings
				image_to_video.SettingsManager.load_config = original_load_config
				image_to_video.SettingsManager.save_config = original_save_config

		self.assertTrue(switched)
		self.assertEqual(next_profile, "PROFILE_2")
		self.assertEqual(saved_settings.get("current_profile"), "PROFILE_2")
		account = saved_config.get("account1") if isinstance(saved_config.get("account1"), dict) else {}
		self.assertTrue(str(account.get("folder_user_data_get_token") or "").endswith("PROFILE_2"))
		self.assertEqual(str(account.get("URL_GEN_TOKEN") or ""), "")


if __name__ == "__main__":
	unittest.main()
