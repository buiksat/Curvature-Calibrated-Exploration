"""Offline behavioral tests for the read-only Claude review runner.

Run with: python -m unittest discover -s tools -p 'test_claude_review.py' -v
"""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
import urllib.error

import claude_review as review


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, path, payload=None):
        self.calls.append((method, path, copy.deepcopy(payload)))
        if not self.responses:
            raise AssertionError("Unexpected API call")
        return self.responses.pop(0)


class OfflineTest(unittest.TestCase):
    def setUp(self):
        # Any accidental attempt to reach a real API fails the test.
        for method in ("urlopen", "build_opener"):
            patcher = mock.patch.object(
                review.urllib.request, method,
                side_effect=AssertionError("Network access is forbidden in offline tests"),
            )
            patcher.start()
            self.addCleanup(patcher.stop)


class RepoFixture(OfflineTest):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory(prefix="claude-review-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.put("paper.tex", "Original claim.\nSecond line.\n")
        self.put("tools/claude_review_prompt.md", "Review the paper and implementation.")
        self.put("experiment.py", "VERSION = 'original'\n")
        self.put("long.txt", "\n".join(f"row {i}" for i in range(650)))
        self.put("unicode.txt", "界" * 30000)
        self.put("data.json", json.dumps({
            "runs": [{"seed": i, "score": i / 10} for i in range(125)],
            "description": "x" * 10000,
        }))
        self.put("binary.bin", b"before\x00after")
        self.put(".env", "TEST_TRACKED_SECRET_DO_NOT_SEND")
        self.put(".aws/credentials", "TEST_AWS_SECRET_DO_NOT_SEND")
        self.put("cert.key", "TEST_PRIVATE_KEY_DO_NOT_SEND")
        secret = self.root / "outside-secret"
        secret.write_text("TEST_EXTERNAL_SECRET_DO_NOT_SEND")
        (self.repo / "outside-link").symlink_to(secret)
        (self.repo / "inside-link").symlink_to("paper.tex")
        self.git("add", ".")
        self.commit("Initial manuscript")
        first_sha = self.git("rev-parse", "HEAD").strip()
        self.git("update-index", "--add", "--cacheinfo", "160000", first_sha, "vendor/submodule")
        self.commit("Record submodule")
        self.manuscript_sha = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-b", "cce-experiments")
        self.put("experiment.py", "VERSION = 'implementation'\n")
        self.commit("Implementation version", "-a")
        self.implementation_sha = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "main")
        self.put("local-secret.txt", "TEST_UNTRACKED_SECRET_DO_NOT_SEND")
        self.snapshot = review.RepoSnapshot(self.repo, "main", "cce-experiments")
        self.output = self.root / "output"
        self.output.mkdir()

    def git(self, *args):
        result = subprocess.run(
            ["git", "-c", "user.name=Offline Test", "-c", "user.email=offline@example.invalid",
             "-c", "commit.gpgsign=false", "-C", str(self.repo), *args],
            check=True, capture_output=True, text=True,
        )
        return result.stdout

    def commit(self, message, *args):
        self.git("commit", *args, "-m", message)

    def put(self, name, content):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)

    def cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = review.main([
                "--repo", str(self.repo), "--implementation-ref", "cce-experiments", *args,
            ])
        return code, stdout.getvalue(), stderr.getvalue()


class SnapshotTests(RepoFixture):
    def test_branch_movement_and_dirty_checkout_do_not_change_pinned_evidence(self):
        self.put("paper.tex", "New claim in a later commit.\n")
        self.commit("Move manuscript branch", "-a")
        self.put("paper.tex", "Uncommitted claim.\n")
        self.assertEqual(self.snapshot.refs["manuscript"]["sha"], self.manuscript_sha)
        self.assertEqual(self.snapshot.refs["implementation"]["sha"], self.implementation_sha)
        self.assertIn("Original claim.", self.snapshot.read_file("manuscript", "paper.tex")["text"])
        self.assertIn("'original'", self.snapshot.read_file("manuscript", "experiment.py")["text"])
        self.assertIn("'implementation'", self.snapshot.read_file("implementation", "experiment.py")["text"])

    def test_secrets_untracked_files_links_and_gitlinks_are_not_exposed(self):
        forbidden = [".env", ".aws/credentials", "cert.key", "local-secret.txt",
                     "inside-link", "outside-link", "vendor/submodule"]
        listed = {entry["path"] for entry in self.snapshot.list_files("manuscript")["files"]}
        for path in forbidden:
            with self.subTest(path=path):
                self.assertNotIn(path, listed)
                with self.assertRaises(review.ReviewError):
                    self.snapshot.read_file("manuscript", path)
        search = self.snapshot.search_files("manuscript", "DO_NOT_SEND")
        self.assertEqual(search["matches"], [])

    def test_paths_and_ref_aliases_cannot_escape_snapshot(self):
        for path in ["../outside-secret", "/etc/passwd", "./paper.tex", "x/../paper.tex",
                     "paper.tex/", "x//paper.tex", "x\\paper.tex", "paper.tex\n"]:
            with self.subTest(path=path), self.assertRaises(review.ReviewError):
                self.snapshot.read_file("manuscript", path)
        with self.assertRaises(review.ReviewError):
            self.snapshot.read_file("HEAD", "paper.tex")
        with self.assertRaises(review.ReviewError):
            self.snapshot.invoke("__getattribute__", {"name": "repo"})

    def test_binary_is_rejected_and_literal_search_reports_skips(self):
        with self.assertRaises(review.ReviewError):
            self.snapshot.read_file("manuscript", "binary.bin")
        result = self.snapshot.search_files("manuscript", "Original claim.")
        self.assertEqual(result["matches"], [{"path": "paper.tex", "line": 1, "text": "Original claim."}])
        self.assertIn("binary.bin", result["skipped"])
        self.assertEqual(self.snapshot.search_files("manuscript", ".*")["matches"], [])

    def test_file_and_line_pagination_cover_every_item_without_duplication(self):
        paths, offset = [], 0
        while offset is not None:
            result = self.snapshot.list_files("manuscript", offset=offset, limit=2)
            paths.extend(item["path"] for item in result["files"])
            offset = result["next_offset"]
        self.assertEqual(paths, sorted(self.snapshot.files["manuscript"]))
        first = self.snapshot.read_file("manuscript", "long.txt", max_lines=999999)
        self.assertEqual(len(first["text"].splitlines()), 400)
        self.assertEqual(first["next_line"], 401)
        second = self.snapshot.read_file("manuscript", "long.txt", start_line=401, max_lines=400)
        self.assertTrue(second["text"].startswith("401: row 400"))
        self.assertIsNone(second["next_line"])

    def test_tool_results_are_byte_bounded_even_for_non_ascii_text(self):
        try:
            result = self.snapshot.invoke("read_file", {"ref": "manuscript", "path": "unicode.txt"})
        except review.ReviewError as exc:
            self.assertIn("64 KiB", str(exc))
        else:
            self.assertLessEqual(len(result.encode("utf-8")), review.MAX_RESULT)

    def test_json_can_be_navigated_without_returning_entire_large_artifact(self):
        overview = self.snapshot.inspect_json("manuscript", "data.json")
        runs = next(item for item in overview["items"] if item["key"] == "runs")
        self.assertEqual(runs["value"], {"type": "list", "length": 125})
        page = self.snapshot.inspect_json("manuscript", "data.json", ["runs"], limit=9999)
        self.assertEqual(len(page["items"]), 100)
        self.assertEqual(page["next_offset"], 100)
        score = self.snapshot.inspect_json("manuscript", "data.json", ["runs", 2, "score"])
        self.assertEqual(score, {"value": 0.2})
        for components in [["runs", -1], ["runs", True], ["missing"], ["runs", "0"]]:
            with self.subTest(components=components), self.assertRaises(review.ReviewError):
                self.snapshot.inspect_json("manuscript", "data.json", components)
        description = self.snapshot.inspect_json("manuscript", "data.json", ["description"])
        self.assertLess(len(description["value"]), 2100)


class ModelTests(OfflineTest):
    def test_default_is_exact_fable_without_silent_substitution(self):
        client = FakeClient([{"data": [{"id": "claude-opus-4-6"}], "has_more": False}])
        with self.assertRaisesRegex(review.ReviewError, "No substitute"):
            review.resolve_model(client)
        self.assertEqual(review.DEFAULT_MODEL, "claude-fable-5-1")
        self.assertEqual([call[0] for call in client.calls], ["GET"])

    def test_model_discovery_traverses_pages_before_resolving_requested_model(self):
        client = FakeClient([
            {"data": [{"id": "older"}], "has_more": True, "last_id": "older"},
            {"data": [{"id": review.DEFAULT_MODEL}], "has_more": False},
        ])
        selected, available = review.resolve_model(client)
        self.assertEqual(selected, review.DEFAULT_MODEL)
        self.assertEqual(set(available), {"older", review.DEFAULT_MODEL})
        self.assertIn("after_id=older", client.calls[1][1])

    def test_nonadvancing_pagination_terminates_without_inference(self):
        client = FakeClient([
            {"data": [], "has_more": True, "last_id": "same"},
            {"data": [], "has_more": True, "last_id": "same"},
        ])
        with self.assertRaisesRegex(review.ReviewError, "pagination"):
            review.resolve_model(client)
        self.assertEqual(len(client.calls), 2)


class APITransportTests(OfflineTest):
    def test_only_fixed_https_host_is_contacted_and_redirects_are_refused(self):
        opener = mock.Mock()
        opener.open.return_value = io.BytesIO(b'{"data": []}')
        with mock.patch.object(review.urllib.request, "build_opener", return_value=opener) as factory:
            result = review.APIClient("test-key").request("GET", "/v1/models?limit=100")
        self.assertEqual(result, {"data": []})
        self.assertEqual(opener.open.call_args.args[0].full_url, "https://api.anthropic.com/v1/models?limit=100")
        handlers = factory.call_args.args
        self.assertEqual(len(handlers), 1)
        self.assertIsNone(handlers[0].redirect_request(None, None, 302, "Found", {}, "https://other.invalid/"))
        for path in ["https://other.invalid/", "//other.invalid/", "/v1/models\nInjected: value"]:
            with self.subTest(path=path), self.assertRaises(review.ReviewError):
                review.APIClient("test-key").request("GET", path)

    def test_http_failure_does_not_retry_or_expose_error_body_credentials(self):
        opener = mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError(
            "https://api.anthropic.com/v1/messages", 401,
            "private-test-key", {"x-api-key": "private-test-key"}, io.BytesIO(b"private-test-key"),
        )
        with mock.patch.object(review.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(review.ReviewError) as caught:
                review.APIClient("private-test-key").request("POST", "/v1/messages", {})
        self.assertIn("401", str(caught.exception))
        self.assertNotIn("private-test-key", str(caught.exception))
        self.assertEqual(opener.open.call_count, 1)

    def test_invalid_credentials_and_non_object_responses_fail_safely(self):
        for key in ["", "test\nkey", "test key", "秘密"]:
            with self.subTest(key=key), self.assertRaises(review.ReviewError):
                review.APIClient(key)
        for body in [b"not json", b"[]", b"x" * (8 * 1024 * 1024 + 1)]:
            opener = mock.Mock()
            opener.open.return_value = io.BytesIO(body)
            with mock.patch.object(review.urllib.request, "build_opener", return_value=opener):
                with self.subTest(length=len(body)), self.assertRaises(review.ReviewError):
                    review.APIClient("test-key").request("GET", "/v1/models")


class ReviewLoopTests(RepoFixture):
    @staticmethod
    def tool_response(name="read_file", arguments=None):
        return {"stop_reason": "tool_use", "usage": {"input_tokens": 10, "output_tokens": 4},
                "content": [{"type": "tool_use", "id": "tool_1", "name": name,
                             "input": arguments or {"ref": "manuscript", "path": "paper.tex"}}]}

    def both_refs_response(self):
        response = self.tool_response()
        response["content"].append({
            "type": "tool_use", "id": "tool_2", "name": "read_file",
            "input": {"ref": "implementation", "path": "experiment.py"},
        })
        return response

    def test_successful_tool_loop_records_evidence_and_completed_review(self):
        client = FakeClient([
            self.both_refs_response(),
            {"stop_reason": "end_turn", "usage": {"input_tokens": 15, "output_tokens": 8},
             "content": [{"type": "text", "text": "Review based on the original claim."}]},
        ])
        result = review.run_review(client, self.snapshot, "Read both refs.", review.DEFAULT_MODEL, self.output, max_turns=2)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["usage"], {"input_tokens": 25, "output_tokens": 12})
        self.assertEqual(result["turns"], 2)
        self.assertEqual(client.calls[1][2]["tool_choice"], {"type": "none"})
        self.assertEqual((self.output / "review.md").read_text(), "Review based on the original claim.\n")
        actual_manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(actual_manifest["refs"]["manuscript"]["sha"], self.manuscript_sha)
        tool_result = client.calls[1][2]["messages"][-1]["content"][0]
        self.assertEqual(tool_result["tool_use_id"], "tool_1")
        self.assertFalse(tool_result["is_error"])
        self.assertIn("Original claim.", json.loads(tool_result["content"])["text"])
        self.assertNotIn("DO_NOT_SEND", json.dumps(client.calls))

    def test_invalid_tool_request_is_reported_to_model_without_reading_host_file(self):
        response = self.both_refs_response()
        response["content"].insert(0, {
            "type": "tool_use", "id": "unsafe_tool", "name": "read_file",
            "input": {"ref": "manuscript", "path": "../outside-secret"},
        })
        client = FakeClient([
            response,
            {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Unable to inspect that path."}]},
        ])
        review.run_review(client, self.snapshot, "Review.", review.DEFAULT_MODEL, self.output)
        result = client.calls[1][2]["messages"][-1]["content"][0]
        self.assertTrue(result["is_error"])
        self.assertNotIn("TEST_EXTERNAL_SECRET", json.dumps(client.calls))

    def test_truncated_final_response_never_becomes_completed_review(self):
        client = FakeClient([{"stop_reason": "max_tokens", "content": [{"type": "text", "text": "Unfinished argument"}]}])
        with self.assertRaisesRegex(review.ReviewError, "max_tokens"):
            review.run_review(client, self.snapshot, "Review.", review.DEFAULT_MODEL, self.output)
        self.assertFalse((self.output / "review.md").exists())
        self.assertIn("INCOMPLETE", (self.output / "partial-review.md").read_text())
        self.assertEqual(json.loads((self.output / "manifest.json").read_text())["status"], "incomplete")

    def test_exhausted_turn_budget_preserves_incomplete_status(self):
        client = FakeClient([self.tool_response()])
        with self.assertRaisesRegex(review.ReviewError, "final writing turn"):
            review.run_review(client, self.snapshot, "Review.", review.DEFAULT_MODEL, self.output, max_turns=1)
        self.assertEqual(len(client.calls), 1)
        self.assertFalse((self.output / "review.md").exists())
        self.assertEqual(json.loads((self.output / "manifest.json").read_text())["status"], "incomplete")

    def test_empty_end_turn_is_not_a_completed_review(self):
        client = FakeClient([{"stop_reason": "end_turn", "content": []}])
        with self.assertRaisesRegex(review.ReviewError, "completed review"):
            review.run_review(client, self.snapshot, "Review.", review.DEFAULT_MODEL, self.output)
        self.assertFalse((self.output / "review.md").exists())

    def test_prose_without_inspecting_both_snapshots_is_incomplete(self):
        client = FakeClient([
            self.tool_response(),
            {"stop_reason": "end_turn", "content": [{"type": "text", "text": "A plausible but unsupported review."}]},
        ])
        with self.assertRaisesRegex(review.ReviewError, "both manuscript and implementation"):
            review.run_review(client, self.snapshot, "Review.", review.DEFAULT_MODEL, self.output)
        self.assertFalse((self.output / "review.md").exists())
        self.assertIn("unsupported", (self.output / "partial-review.md").read_text())


class CLITests(RepoFixture):
    def test_defaults_pin_revised_implementation_even_when_historical_ref_exists(self):
        self.git("update-ref", "refs/remotes/origin/cce-experiments", self.manuscript_sha)
        self.git("update-ref", "refs/remotes/origin/cce-review-revisions", self.implementation_sha)
        snapshot = review.RepoSnapshot(self.repo)
        self.assertEqual(snapshot.refs["implementation"], {
            "ref": "origin/cce-review-revisions", "sha": self.implementation_sha,
        })
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = review.main(["--repo", str(self.repo), "--prepare-only", "--output", str(self.output)])
        self.assertEqual(code, 0)
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(manifest["refs"]["implementation"], snapshot.refs["implementation"])

    def test_missing_revised_ref_does_not_fall_back_to_historical_branch(self):
        self.git("update-ref", "refs/remotes/origin/cce-experiments", self.implementation_sha)
        stderr = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            code = review.main(["--repo", str(self.repo), "--prepare-only", "--output", str(self.output)])
        self.assertEqual(code, 1)
        self.assertIn("Git read failed", stderr.getvalue())
        self.assertFalse((self.output / "manifest.json").exists())

    def test_prepare_only_is_offline_preserves_checkout_and_records_exact_refs(self):
        before = self.git("status", "--porcelain=v1", "--untracked-files=all")
        with mock.patch.dict(os.environ, {}, clear=True):
            code, stdout, stderr = self.cli("--prepare-only", "--output", str(self.output))
        self.assertEqual(code, 0, stderr)
        self.assertIn("no inference requested", stdout)
        self.assertEqual(self.git("status", "--porcelain=v1", "--untracked-files=all"), before)
        manifest = json.loads((self.output / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "prepared")
        self.assertFalse(manifest["access_verified"])
        self.assertEqual(manifest["refs"]["implementation"]["sha"], self.implementation_sha)
        self.assertNotIn(".env", manifest["tracked_files"]["manuscript"])

    def test_output_cannot_be_checkout_or_symlink_into_checkout(self):
        alias = self.root / "repo-alias"
        alias.symlink_to(self.repo, target_is_directory=True)
        for output in [self.repo, self.repo / "review-output", alias / "review-output"]:
            with self.subTest(output=output):
                code, _, stderr = self.cli("--prepare-only", "--output", str(output))
                self.assertEqual(code, 1)
                self.assertIn("outside the checkout", stderr)
        self.assertFalse((self.repo / "review-output").exists())

    def test_existing_review_output_is_never_overwritten(self):
        existing = self.output / "review.md"
        existing.write_text("Existing review")
        code, _, stderr = self.cli("--prepare-only", "--output", str(self.output))
        self.assertEqual(code, 1)
        self.assertIn("not empty", stderr)
        self.assertEqual(existing.read_text(), "Existing review")

    def test_missing_key_preserves_preparation_but_does_not_call_api(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(review, "APIClient") as client:
            code, _, stderr = self.cli("--output", str(self.output))
        self.assertEqual(code, 1)
        self.assertIn("ANTHROPIC_API_KEY", stderr)
        client.assert_not_called()
        self.assertEqual(json.loads((self.output / "manifest.json").read_text())["status"], "blocked")

    def test_access_check_lists_models_without_inference_or_storing_api_key(self):
        client = FakeClient([{"data": [{"id": review.DEFAULT_MODEL}], "has_more": False}])
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-do-not-persist"}), \
                mock.patch.object(review, "APIClient", return_value=client):
            code, stdout, stderr = self.cli("--check-access", "--output", str(self.output))
        self.assertEqual(code, 0, stderr)
        self.assertIn(review.DEFAULT_MODEL, stdout)
        self.assertTrue(client.calls)
        self.assertTrue(all(call[0] == "GET" for call in client.calls))
        self.assertNotIn("test-key-do-not-persist", (self.output / "manifest.json").read_text())
        self.assertNotIn("test-key-do-not-persist", stdout + stderr)

    def test_missing_model_lists_available_choices_without_substitution_or_inference(self):
        client = FakeClient([{"data": [{"id": "available-other-model"}], "has_more": False}])
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
                mock.patch.object(review, "APIClient", return_value=client):
            code, stdout, stderr = self.cli("--check-access", "--output", str(self.output))
        self.assertEqual(code, 1)
        self.assertIn("available-other-model", stdout + stderr)
        self.assertIn("No substitute", stderr)
        self.assertTrue(all(call[0] == "GET" for call in client.calls))
        self.assertEqual(json.loads((self.output / "manifest.json").read_text())["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
