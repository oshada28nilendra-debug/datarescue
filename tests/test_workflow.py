import tempfile
import unittest
from pathlib import Path

from datarescue.dataset import Error, digest, load_csv
from datarescue.workflow import approved_result, model_context, preview, propose


class FakeProvider:
    mode = "test_double"
    calls = 0
    usage = {}

    def __init__(self, result):
        self.result = result
        self.tasks = []

    def complete(self, task):
        self.calls += 1
        self.tasks.append(task)
        return self.result


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "orders.csv"
        self.path.write_text("id,status\n001, pending \n002,pendng\n002,pendng\n")
        self.table = load_csv(self.path)

    def test_offline_proposals_are_unapproved_and_source_bound(self):
        p = propose(self.table)
        self.assertEqual(p["mode"], "offline_rules")
        self.assertEqual(p["source_sha256"], self.table.source_sha256)
        self.assertEqual(p["model"]["calls"], 0)
        self.assertTrue(p["proposals"])
        self.assertNotIn("approved", p["proposals"][0])

    def test_review_accept_reject_modify_and_sequential_preview(self):
        p = propose(self.table)
        first = next(x for x in p["proposals"] if x["operation"]["kind"] == "trim")
        review = {
            "proposal_digest": p["digest"],
            "reviewer": "Fixture reviewer",
            "decisions": [
                {
                    "id": first["id"],
                    "decision": "modify",
                    "operation": {
                        "kind": "replace_exact",
                        "column": "status",
                        "mapping": {"pendng": "pending"},
                    },
                }
            ],
        }
        result = preview(self.table, p, review)
        self.assertEqual(len(result["operations"]), 1)
        self.assertEqual(result["steps"][0]["changed_cells"], 2)
        self.assertEqual(result["source_sha256"], self.table.source_sha256)

    def test_default_reject_and_explicit_false_approval(self):
        p = propose(self.table)
        result = preview(self.table, p, {"proposal_digest": p["digest"], "reviewer": "R", "decisions": []})
        self.assertEqual(result["operations"], [])
        with self.assertRaises(Error):
            approved_result(
                self.table, result, {"preview_digest": result["digest"], "approve": False, "reviewer": "R"}
            )

    def test_approved_preview_recomputes_and_preserves_input(self):
        p = propose(self.table)
        r = {
            "proposal_digest": p["digest"],
            "reviewer": "R",
            "decisions": [{"id": x["id"], "decision": "accept"} for x in p["proposals"]],
        }
        result = preview(self.table, p, r)
        cleaned = approved_result(
            self.table, result, {"preview_digest": result["digest"], "approve": True, "reviewer": "R"}
        )
        self.assertEqual(self.table.rows[0][1], " pending ")
        self.assertEqual(len(cleaned.rows), 2)
        self.assertEqual(cleaned.rows[0], ("001", "pending"))

    def test_tampered_preview_even_if_rehashed_is_rejected(self):
        p = propose(self.table)
        r = {"proposal_digest": p["digest"], "reviewer": "R", "decisions": []}
        result = preview(self.table, p, r)
        result["output_sha256"] = "fake"
        result["digest"] = digest({k: v for k, v in result.items() if k != "digest"})
        with self.assertRaises(Error):
            approved_result(
                self.table, result, {"preview_digest": result["digest"], "approve": True, "reviewer": "R"}
            )

    def test_changed_source_or_decision_digest_is_rejected(self):
        p = propose(self.table)
        with self.assertRaises(Error):
            preview(self.table, p, {"proposal_digest": "wrong", "reviewer": "R", "decisions": []})
        self.path.write_text("id,status\n999,new\n")
        with self.assertRaises(Error):
            preview(
                load_csv(self.path), p, {"proposal_digest": p["digest"], "reviewer": "R", "decisions": []}
            )

    def test_duplicate_ids_and_unknown_modification_parameters_fail(self):
        p = propose(self.table)
        for decisions in [
            [{"id": "p1", "decision": "accept"}] * 2,
            [{"id": "unknown", "decision": "accept"}],
            [{"id": "p1", "decision": "modify", "operation": {"kind": "python"}}],
            [{"id": "p1", "decision": []}],
        ]:
            with self.assertRaises(Error):
                preview(
                    self.table, p, {"proposal_digest": p["digest"], "reviewer": "R", "decisions": decisions}
                )

    def test_model_values_are_opt_in_and_only_chosen_columns_are_shared(self):
        self.assertNotIn("pendng", str(model_context(self.table, [])))
        shared = model_context(self.table, ["status"])
        self.assertIn("pendng", str(shared))
        self.assertNotIn("001", str(shared))
        with self.assertRaises(Error):
            model_context(self.table, ["missing"])

    def test_unsupported_model_code_rejected_but_valid_proposals_retained(self):
        provider = FakeProvider(
            {
                "proposals": [
                    {"operation": {"kind": "python", "code": "print(1)"}, "reason": "Unsupported"},
                    {
                        "operation": {
                            "kind": "replace_exact",
                            "column": "status",
                            "mapping": {"pendng": "pending"},
                        },
                        "reason": "Possible spelling error; user must confirm.",
                    },
                ]
            }
        )
        p = propose(self.table, provider=provider, share_columns=["status"])
        self.assertEqual(len(p["rejected"]), 1)
        self.assertEqual(len(p["proposals"]), 1)
        self.assertEqual(p["mode"], "test_double")
        self.assertEqual(p["proposals"][0]["operation"]["mapping"], {"pendng": "pending"})

    def test_model_envelope_and_failures_do_not_turn_into_offline_success(self):
        p = propose(self.table, provider=FakeProvider({"proposals": "bad"}))
        self.assertTrue(p["errors"])
        self.assertEqual(p["proposals"], [])

    def test_imported_recipe_is_new_unapproved_proposal_for_current_source(self):
        p = propose(self.table, imported={"operations": [{"kind": "trim", "column": "status"}]})
        self.assertEqual(p["mode"], "imported_recipe")
        self.assertEqual(p["source_sha256"], self.table.source_sha256)
        self.assertEqual(p["proposals"][0]["operation"]["kind"], "trim")

    def test_duplicate_removal_after_trim_is_visible(self):
        self.path.write_text("a\n x \nx\n")
        t = load_csv(self.path)
        p = propose(
            t, imported={"operations": [{"kind": "trim", "column": "a"}, {"kind": "drop_exact_duplicates"}]}
        )
        r = {
            "proposal_digest": p["digest"],
            "reviewer": "R",
            "decisions": [{"id": x["id"], "decision": "accept"} for x in p["proposals"]],
        }
        result = preview(t, p, r)
        self.assertEqual(result["steps"][1]["removed_records"], [2])


if __name__ == "__main__":
    unittest.main()
