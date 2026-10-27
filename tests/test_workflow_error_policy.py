from __future__ import annotations

import unittest

from prompt_utils import assess_prompt_quality

from workflow_error_policy import (
    ERROR_KIND_CONTENT_FILTER,
    ERROR_KIND_QUOTA_EXHAUSTED,
    ERROR_KIND_RECAPTCHA_FAILED,
    IMAGE_PROMPT_MAX_SAFE_CHARS,
    RECAPTCHA_CIRCUIT_BREAKER_SECONDS,
    RECAPTCHA_CIRCUIT_BREAKER_THRESHOLD,
    classify_api_error,
    is_image_prompt_too_long,
    recaptcha_backoff_seconds,
)


class _MaxRng:
    def randint(self, low: int, high: int) -> int:
        return high


class _MinRng:
    def randint(self, low: int, high: int) -> int:
        return low


class WorkflowErrorPolicyTests(unittest.TestCase):
    def test_classifies_recaptcha_evaluation_failed(self) -> None:
        self.assertEqual(
            classify_api_error("403", "reCAPTCHA evaluation failed"),
            ERROR_KIND_RECAPTCHA_FAILED,
        )

    def test_classifies_quota_exhausted_and_429(self) -> None:
        self.assertEqual(
            classify_api_error("429", "reCAPTCHA evaluation failed"),
            ERROR_KIND_QUOTA_EXHAUSTED,
        )
        self.assertEqual(
            classify_api_error("", "Resource has been exhausted (e.g. check quota).", status=429),
            ERROR_KIND_QUOTA_EXHAUSTED,
        )

    def test_content_filter_still_wins(self) -> None:
        self.assertEqual(
            classify_api_error("3", "PUBLIC_ERROR_DANGER_FILTER"),
            ERROR_KIND_CONTENT_FILTER,
        )

    def test_recaptcha_backoff_sequence_caps_at_third_value(self) -> None:
        self.assertEqual(recaptcha_backoff_seconds(1, rng=_MinRng()), 20)
        self.assertEqual(recaptcha_backoff_seconds(1, rng=_MaxRng()), 35)
        self.assertEqual(recaptcha_backoff_seconds(2, rng=_MinRng()), 60)
        self.assertEqual(recaptcha_backoff_seconds(2, rng=_MaxRng()), 90)
        self.assertEqual(recaptcha_backoff_seconds(3, rng=_MinRng()), 180)
        self.assertEqual(recaptcha_backoff_seconds(99, rng=_MaxRng()), 300)

    def test_recaptcha_circuit_breaker_is_short_enough_for_batch_runs(self) -> None:
        self.assertEqual(RECAPTCHA_CIRCUIT_BREAKER_THRESHOLD, 4)
        self.assertEqual(RECAPTCHA_CIRCUIT_BREAKER_SECONDS, 300)

    def test_image_prompt_length_preflight_threshold(self) -> None:
        self.assertEqual(IMAGE_PROMPT_MAX_SAFE_CHARS, 1500)
        self.assertFalse(is_image_prompt_too_long("x" * 1500))
        self.assertTrue(is_image_prompt_too_long("x" * 1501))

    def test_image_prompt_quality_uses_1500_hard_max(self) -> None:
        at_limit = assess_prompt_quality("x" * 1500, mode="image")
        over_limit = assess_prompt_quality("x" * 1501, mode="image")

        self.assertTrue(at_limit["in_safe_range"])
        self.assertEqual(at_limit["ideal_range"], "150-400")
        self.assertFalse(over_limit["in_safe_range"])
        self.assertIn("1500", over_limit["warning"] or "")


if __name__ == "__main__":
    unittest.main()
