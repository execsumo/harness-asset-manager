from __future__ import annotations

import unittest

from harness_asset_manager.application.drift import classify_drift


class ClassifyDriftTests(unittest.TestCase):
    """The decision table of plan-auto-adoption.md §4, one test per row.

    Pure function, no filesystem: the classification is the part that must be
    reviewable on its own, because every automatic action across every family
    that adopts this table will be gated on it.
    """

    def test_row_1_no_baseline_is_a_collision(self) -> None:
        self.assertEqual(
            classify_drift(baseline_sha256=None, harness_sha256="sha256:a", store_sha256="sha256:b"),
            "collision",
        )

    def test_row_2_identical_content_is_a_clean_clobber(self) -> None:
        self.assertEqual(
            classify_drift(
                baseline_sha256="sha256:old",
                harness_sha256="sha256:same",
                store_sha256="sha256:same",
            ),
            "clobber_clean",
        )

    def test_row_3_store_untouched_since_baseline_is_one_sided(self) -> None:
        self.assertEqual(
            classify_drift(
                baseline_sha256="sha256:linked",
                harness_sha256="sha256:edited",
                store_sha256="sha256:linked",
            ),
            "clobber_one_sided",
        )

    def test_row_4_both_sides_moved_is_a_two_sided_conflict(self) -> None:
        self.assertEqual(
            classify_drift(
                baseline_sha256="sha256:linked",
                harness_sha256="sha256:edited",
                store_sha256="sha256:also-edited",
            ),
            "two_sided_conflict",
        )

    def test_unreadable_harness_side_degrades_to_collision(self) -> None:
        self.assertEqual(
            classify_drift(
                baseline_sha256="sha256:linked",
                harness_sha256=None,
                store_sha256="sha256:linked",
            ),
            "collision",
        )

    def test_unreadable_store_side_degrades_to_collision(self) -> None:
        self.assertEqual(
            classify_drift(
                baseline_sha256="sha256:linked",
                harness_sha256="sha256:linked",
                store_sha256=None,
            ),
            "collision",
        )


if __name__ == "__main__":
    unittest.main()
