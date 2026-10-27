from __future__ import annotations

import time
import unittest

import pytest

_generate_image = pytest.importorskip(
    "A_workflow_generate_image",
    reason="legacy desktop image workflow is not part of the Muse2API runtime",
)
AdaptiveImagePacer = _generate_image.AdaptiveImagePacer
GenerateImageWorkflow = _generate_image.GenerateImageWorkflow
from workflow_error_policy import IMAGE_PROMPT_MAX_SAFE_CHARS, is_image_prompt_too_long


class _Collector:
    def __init__(self) -> None:
        self.reloads = 0
        self.restarts = 0

    async def _reload_project_page(self):
        self.reloads += 1

    async def restart_browser(self):
        self.restarts += 1


class GenerateImageCooldownTests(unittest.IsolatedAsyncioTestCase):
    async def test_global_cooldown_gate_waits_before_continuing(self) -> None:
        workflow = GenerateImageWorkflow(project_name="test", project_data={})
        waits: list[float] = []
        workflow._global_cooldown_until = time.time() + 30

        async def fake_sleep(seconds):
            waits.append(float(seconds))
            workflow._global_cooldown_until = 0
            return True

        workflow._sleep_with_stop = fake_sleep

        self.assertTrue(await workflow._wait_for_global_cooldown("test gate"))
        self.assertTrue(waits)
        self.assertLessEqual(waits[0], 5.0)

    async def test_recaptcha_counter_is_workflow_level(self) -> None:
        workflow = GenerateImageWorkflow(project_name="test", project_data={})
        collector = _Collector()
        seen_counts: list[int] = []

        async def fake_wait(reason=""):
            workflow._global_cooldown_until = 0
            return True

        def fake_set_global_cooldown(seconds):
            seen_counts.append(workflow._recaptcha_consecutive_failures)
            workflow._global_cooldown_until = 0

        workflow._wait_for_global_cooldown = fake_wait
        workflow._set_global_cooldown = fake_set_global_cooldown

        self.assertTrue(await workflow._apply_recaptcha_cooldown(collector))
        self.assertTrue(await workflow._apply_recaptcha_cooldown(collector))
        self.assertTrue(await workflow._apply_recaptcha_cooldown(collector))

        self.assertEqual(seen_counts[:3], [1, 2, 3])
        self.assertEqual(collector.reloads, 1)
        self.assertEqual(collector.restarts, 1)

    async def test_recaptcha_circuit_breaker_uses_five_minute_cooldown(self) -> None:
        workflow = GenerateImageWorkflow(project_name="test", project_data={})
        collector = _Collector()
        seen_seconds: list[int] = []

        async def fake_wait(reason=""):
            workflow._global_cooldown_until = 0
            return True

        def fake_set_global_cooldown(seconds):
            seen_seconds.append(int(seconds))
            workflow._global_cooldown_until = 0

        workflow._wait_for_global_cooldown = fake_wait
        workflow._set_global_cooldown = fake_set_global_cooldown

        for _ in range(4):
            self.assertTrue(await workflow._apply_recaptcha_cooldown(collector))

        self.assertEqual(seen_seconds[-1], 300)

    def test_adaptive_pacer_balances_speed_and_probe_mode(self) -> None:
        pacer = AdaptiveImagePacer(6, output_count=1, enabled=True)

        self.assertEqual(pacer.current_limit(), 3)
        self.assertEqual(pacer.max_cap, 6)

        pacer.record_success()
        pacer.record_success()
        pacer.record_success()
        self.assertEqual(pacer.current_limit(), 4)

        pacer.record_recaptcha_failure()
        self.assertEqual(pacer.current_limit(), 1)
        self.assertTrue(pacer.probe_mode)

        self.assertFalse(pacer.record_success())
        self.assertTrue(pacer.record_success())
        self.assertFalse(pacer.probe_mode)

    def test_adaptive_pacer_caps_total_requested_outputs(self) -> None:
        pacer = AdaptiveImagePacer(10, output_count=4, enabled=True)

        self.assertEqual(pacer.max_cap, 2)
        self.assertEqual(pacer.current_limit(), 2)


    def test_retry_cooldown_status_does_not_hold_inflight_slot(self) -> None:
        workflow = GenerateImageWorkflow(project_name="test", project_data={})
        workflow._active_prompt_ids = {"1"}
        workflow._load_state_json = lambda: {
            "prompts": {
                "1": {"statuses": ["RETRY_COOLDOWN"]},
            }
        }

        self.assertEqual(workflow._count_in_progress_from_state(), 0)

    def test_stale_active_state_does_not_hold_adaptive_slot(self) -> None:
        workflow = GenerateImageWorkflow(project_name="test", project_data={})
        workflow._image_pacer = AdaptiveImagePacer(3)
        workflow._active_prompt_ids = {"1"}
        workflow._load_state_json = lambda: {
            "prompts": {
                "1": {"statuses": ["ACTIVE"]},
            }
        }

        self.assertEqual(workflow._count_in_progress(), 0)

    def test_gem_pix_2_uses_single_flight_limit(self) -> None:
        workflow = GenerateImageWorkflow(project_name="test", project_data={})

        self.assertEqual(workflow._get_max_in_flight("GEM_PIX_2", 6), 1)

    def test_prompt_1500_regression(self) -> None:
        self.assertEqual(IMAGE_PROMPT_MAX_SAFE_CHARS, 1500)
        self.assertFalse(is_image_prompt_too_long("x" * 1500))
        self.assertTrue(is_image_prompt_too_long("x" * 1501))


if __name__ == "__main__":
    unittest.main()
