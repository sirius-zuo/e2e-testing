import fcntl
import json
import multiprocessing
import tempfile
import time
import unittest
from pathlib import Path

from protocol.v1.e2e_protocol import (
    ProtocolError,
    new_manifest,
    save_manifest,
    transition,
    validate_manifest,
)


def _transition_in_process(path, started, result):
    started.put(None)
    try:
        result.put(("saved", transition(path, 1, "planned", [])))
    except ProtocolError as error:
        result.put(("error", str(error)))


class ProtocolTests(unittest.TestCase):
    def test_new_manifest_is_valid_and_defaults_to_generate(self):
        manifest = new_manifest("/workspace/app")
        self.assertEqual(manifest["protocol_version"], "1.0")
        self.assertEqual(manifest["mode"], "generate")
        self.assertEqual(manifest["autonomy"]["mode"], "explicit")
        self.assertFalse(manifest["autonomy"]["auto_repair"])
        self.assertEqual(validate_manifest(manifest), [])

    def test_save_increments_revision_and_rejects_stale_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".e2e" / "manifest.json"
            saved = save_manifest(path, new_manifest(tmp), expected_revision=None)
            self.assertEqual(saved["revision"], 1)
            saved = transition(path, 1, "planned", [])
            self.assertEqual(saved["revision"], 2)
            with self.assertRaisesRegex(ProtocolError, "revision conflict"):
                transition(path, 1, "ready-for-adapter", [])

    def test_invalid_transition_is_rejected_without_file_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            save_manifest(path, new_manifest(tmp), None)
            before = path.read_text()
            with self.assertRaisesRegex(ProtocolError, "invalid transition"):
                transition(path, 1, "verified", [])
            self.assertEqual(path.read_text(), before)

    def test_duplicate_ids_and_secret_values_are_rejected(self):
        manifest = new_manifest("/workspace/app")
        manifest["journeys"] = [
            {"id": "journey-login", "status": "planned"},
            {"id": "journey-login", "status": "planned"},
        ]
        manifest["target"]["password"] = "plaintext"
        errors = validate_manifest(manifest)
        self.assertTrue(any("duplicate" in error for error in errors))
        self.assertTrue(any("secret value" in error for error in errors))

    def test_multiple_next_actions_remain_ordered(self):
        manifest = new_manifest("/workspace/app")
        manifest["journeys"] = [
            {"id": "j1", "status": "planned"},
            {"id": "j2", "status": "planned"},
        ]
        manifest["next_actions"] = [
            {"id": "action-auth", "capability": "provide-test-credentials", "journey_ids": ["j1"]},
            {"id": "action-fix", "capability": "fix-product-defect", "journey_ids": ["j2"]},
        ]
        self.assertEqual(validate_manifest(manifest), [])
        self.assertEqual(manifest["next_actions"][0]["id"], "action-auth")

    def test_save_waits_for_another_writer_holding_the_manifest_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            save_manifest(path, new_manifest(tmp), None)
            lock_path = path.with_name(f".{path.name}.lock")
            with lock_path.open("w") as lock_file:
                fcntl.flock(lock_file, fcntl.LOCK_EX)
                context = multiprocessing.get_context("spawn")
                started = context.Queue()
                result = context.Queue()
                process = context.Process(
                    target=_transition_in_process,
                    args=(str(path), started, result),
                )
                process.start()
                started.get(timeout=5)
                time.sleep(0.2)
                self.assertEqual(json.loads(path.read_text())["revision"], 1)
                fcntl.flock(lock_file, fcntl.LOCK_UN)
                outcome, value = result.get(timeout=5)
                process.join(timeout=5)
                self.assertEqual(process.exitcode, 0)
                self.assertEqual(outcome, "saved")
                self.assertEqual(value["revision"], 2)


if __name__ == "__main__":
    unittest.main()
