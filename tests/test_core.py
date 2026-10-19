import tempfile
import unittest
from pathlib import Path

from datarescue.dataset import Error, load_csv, profile
from datarescue.engine import transform, validate_operation


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "input.csv"

    def table(self, content):
        self.path.write_text(content, encoding="utf-8")
        return load_csv(self.path)

    def test_preserves_strings_leading_zero_ids_and_multiline_values(self):
        t = self.table('id,note\n001,"line one\nline two"\n')
        self.assertEqual(t.rows, (("001", "line one\nline two"),))
        self.assertEqual(t.records, (1,))

    def test_rejects_bad_headers_ragged_and_malformed_csv(self):
        for content in ["a,a\n1,2\n", ",b\n1,2\n", "a,b\n1\n", 'a\n"unterminated', ""]:
            with self.subTest(content=content), self.assertRaises(Error):
                self.table(content)

    def test_rejects_binary_oversized_and_symlink_input(self):
        for data in [b"\xff", b"a\x00b", b"x" * 2_000_001]:
            self.path.write_bytes(data)
            with self.assertRaises(Error):
                load_csv(self.path)
        self.table("a\n1\n")
        link = self.path.parent / "link.csv"
        link.symlink_to(self.path)
        with self.assertRaises(Error):
            load_csv(link)

    def test_profile_missing_duplicates_and_mixed_types(self):
        t = self.table("id,amount,date\n001,10,01/02/2026\n002,bad,2026-10-18\n002,bad,2026-10-18\n003, ,\n")
        p = profile(t)
        self.assertEqual(p["duplicate_rows"], 1)
        self.assertEqual(p["columns"]["id"]["leading_zero_values"], 4)
        self.assertEqual(p["columns"]["amount"]["missing"], 1)
        self.assertEqual(p["columns"]["amount"]["inferred_type"], "mixed")
        self.assertEqual(p["columns"]["date"]["ambiguous_dates"], 1)

    def test_trim_does_not_mutate_input_and_reports_original_record(self):
        t = self.table("id,status\n001, pending \n002,done\n")
        result, delta = transform(t, {"kind": "trim", "column": "status"})
        self.assertEqual(t.rows[0][1], " pending ")
        self.assertEqual(result.rows[0], ("001", "pending"))
        self.assertEqual(
            delta["changes"], [{"record": 1, "column": "status", "before": " pending ", "after": "pending"}]
        )

    def test_explicit_mapping_does_not_guess_other_values(self):
        t = self.table("status\npendng\nPending\nunknown\n")
        result, delta = transform(
            t, {"kind": "replace_exact", "column": "status", "mapping": {"pendng": "pending"}}
        )
        self.assertEqual(result.rows, (("pending",), ("Pending",), ("unknown",)))
        self.assertEqual(delta["changed_cells"], 1)

    def test_blank_markers_are_exact_not_universal_missing_inference(self):
        t = self.table("country\nNA\nN/A\nNULL\n")
        result, _ = transform(t, {"kind": "blank_markers", "column": "country", "markers": ["N/A", "NULL"]})
        self.assertEqual(result.rows, (("NA",), ("",), ("",)))

    def test_explicit_date_format_keeps_invalid_values_and_counts_them(self):
        t = self.table("date\n01/02/2026\n31/02/2026\n\n")
        result, delta = transform(t, {"kind": "date_iso", "column": "date", "format": "%d/%m/%Y"})
        self.assertEqual(result.rows[:2], (("2026-02-01",), ("31/02/2026",)))
        self.assertEqual(delta["invalid_values"], 1)

    def test_case_transformation_is_explicit(self):
        t = self.table("status\nDONE\nPending\n")
        result, _ = transform(t, {"kind": "case", "column": "status", "mode": "lower"})
        self.assertEqual(result.rows, (("done",), ("pending",)))

    def test_duplicate_removal_keeps_first_and_original_record_ids(self):
        t = self.table("id,status\n001,done\n001,done\n002,done\n")
        result, delta = transform(t, {"kind": "drop_exact_duplicates"})
        self.assertEqual(result.records, (1, 3))
        self.assertEqual(delta["removed_records"], [2])

    def test_unknown_code_and_malformed_params_fail_closed(self):
        for op in [
            {"kind": "python", "code": '__import__("os")'},
            {"kind": []},
            {"kind": "trim", "column": "id", "approved": True},
            {"kind": "replace_exact", "column": "id", "mapping": []},
            {"kind": "date_iso", "column": "id", "format": "%y"},
            {"kind": "trim", "column": "missing"},
        ]:
            with self.subTest(op=op), self.assertRaises(Error):
                validate_operation(op, ("id",))

    def test_cell_budget(self):
        with self.assertRaises(Error):
            self.table("a\n" + "x" * 4097 + "\n")


if __name__ == "__main__":
    unittest.main()
