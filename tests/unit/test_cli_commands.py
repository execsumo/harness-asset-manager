"""End-to-end coverage for the headless asset commands.

These drive ``cli.main.main`` the way a script on a VPS would: real argv, a real
container over a temp home, and assertions on stdout plus the exit code. Anything
that only checks the parser would miss the part that actually matters — that the
handler reaches the same services the HTTP routers use.
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from harness_asset_manager.cli.main import build_parser, main, normalize_argv
from harness_asset_manager.paths import APP_NAME
from tests.support.fake_home import create_fake_home_spec


class CliCommandTestCase(unittest.TestCase):
    """Runs commands against an isolated fake home."""

    def setUp(self) -> None:
        self._tempdir = TemporaryDirectory(prefix="harnessam-cli-tests-")
        self.addCleanup(self._tempdir.cleanup)
        self.spec = create_fake_home_spec(Path(self._tempdir.name))
        env_patch = mock.patch.dict("os.environ", self.spec.env(), clear=True)
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def run_json(self, *argv: str) -> object:
        code, out, err = self.run_cli(*argv, "--json")
        self.assertEqual(code, 0, msg=err or out)
        return json.loads(out)


class ParserTests(unittest.TestCase):
    def test_asset_groups_are_not_treated_as_serve_arguments(self) -> None:
        for group in (
            "skills",
            "agents",
            "mcp",
            "hooks",
            "permissions",
            "commands",
            "settings",
            "refresh",
        ):
            self.assertEqual(normalize_argv([group, "list"])[0], group)

    def test_bare_server_flags_still_imply_serve(self) -> None:
        self.assertEqual(normalize_argv(["--port", "9000"]), ["serve", "--port", "9000"])
        self.assertEqual(normalize_argv([]), ["serve"])

    def test_runtime_commands_have_no_asset_handler(self) -> None:
        # `serve`/`start`/`stop`/`status`/`token` must keep their own dispatch path so they
        # never pay for building a backend container.
        for command in ("serve", "start", "stop", "status", "token"):
            args = build_parser().parse_args([command])
            self.assertIsNone(getattr(args, "handler", None), msg=command)

    def test_refresh_dispatches_through_the_asset_runner(self) -> None:
        args = build_parser().parse_args(["refresh"])
        self.assertIsNotNone(getattr(args, "handler", None))


class ResolvedTrustedHostsTests(unittest.TestCase):
    """Priority: explicit CLI/env wins outright; auto-detect only fills a gap."""

    def _args(self, trusted_hosts: list[str] | None = None) -> mock.Mock:
        return mock.Mock(trusted_hosts=trusted_hosts or [])

    def test_env_var_is_comma_split_and_stripped(self) -> None:
        from harness_asset_manager.cli.main import resolved_trusted_hosts

        env = {"HARNESS_ASSET_MANAGER_TRUSTED_HOSTS": " foo.ts.net, bar.example ,"}
        self.assertEqual(resolved_trusted_hosts(self._args(), env), ("foo.ts.net", "bar.example"))

    def test_cli_flags_merge_with_env_and_dedupe(self) -> None:
        from harness_asset_manager.cli.main import resolved_trusted_hosts

        env = {"HARNESS_ASSET_MANAGER_TRUSTED_HOSTS": "foo.ts.net"}
        result = resolved_trusted_hosts(self._args(["bar.example", "foo.ts.net"]), env)
        self.assertEqual(result, ("foo.ts.net", "bar.example"))

    def test_explicit_config_skips_auto_detection(self) -> None:
        from harness_asset_manager.cli.main import resolved_trusted_hosts

        with mock.patch(
            "harness_asset_manager.runtime.tailscale.detect_tailnet_dns_name",
            side_effect=AssertionError("must not be called when something explicit is set"),
        ):
            result = resolved_trusted_hosts(self._args(["bar.example"]), {})
        self.assertEqual(result, ("bar.example",))

    def test_falls_back_to_auto_detected_tailnet_hostname(self) -> None:
        from harness_asset_manager.cli.main import resolved_trusted_hosts

        with mock.patch(
            "harness_asset_manager.runtime.tailscale.detect_tailnet_dns_name",
            return_value="my-mac.tailnet-name.ts.net",
        ):
            result = resolved_trusted_hosts(self._args(), {})
        self.assertEqual(result, ("my-mac.tailnet-name.ts.net",))

    def test_nothing_configured_and_nothing_detected_yields_empty(self) -> None:
        from harness_asset_manager.cli.main import resolved_trusted_hosts

        with mock.patch(
            "harness_asset_manager.runtime.tailscale.detect_tailnet_dns_name",
            return_value=None,
        ):
            result = resolved_trusted_hosts(self._args(), {})
        self.assertEqual(result, ())


class ResolvedTailnetPortTests(unittest.TestCase):
    """Priority: explicit --tailnet-port wins; else $HAM_TAILNET_PORT; else 7443."""

    def _args(self, tailnet_port: int | None = None) -> mock.Mock:
        return mock.Mock(tailnet_port=tailnet_port)

    def test_explicit_flag_wins(self) -> None:
        from harness_asset_manager.cli.main import resolved_tailnet_port

        self.assertEqual(resolved_tailnet_port(self._args(9443), {"HAM_TAILNET_PORT": "1111"}), 9443)

    def test_falls_back_to_env_var(self) -> None:
        from harness_asset_manager.cli.main import resolved_tailnet_port

        self.assertEqual(resolved_tailnet_port(self._args(), {"HAM_TAILNET_PORT": "9000"}), 9000)

    def test_defaults_to_7443(self) -> None:
        from harness_asset_manager.cli.main import resolved_tailnet_port

        self.assertEqual(resolved_tailnet_port(self._args(), {}), 7443)

    def test_malformed_env_var_falls_back_to_default(self) -> None:
        from harness_asset_manager.cli.main import resolved_tailnet_port

        self.assertEqual(resolved_tailnet_port(self._args(), {"HAM_TAILNET_PORT": "not-a-port"}), 7443)


class TailnetFlagParsingTests(unittest.TestCase):
    def test_tailnet_defaults_to_enabled(self) -> None:
        args = build_parser().parse_args(["serve"])
        self.assertTrue(args.tailnet)
        self.assertIsNone(args.tailnet_port)

    def test_no_tailnet_disables_it(self) -> None:
        args = build_parser().parse_args(["serve", "--no-tailnet"])
        self.assertFalse(args.tailnet)

    def test_tailnet_port_flag_is_parsed(self) -> None:
        args = build_parser().parse_args(["serve", "--tailnet-port", "9443"])
        self.assertEqual(args.tailnet_port, 9443)


class TokenCommandTests(CliCommandTestCase):
    def test_token_reads_and_generates_token(self) -> None:
        code, out, err = self.run_cli("token")
        self.assertEqual(code, 0, msg=err)
        token = out.strip()
        self.assertTrue(len(token) > 20)

        # Running again prints the same token
        code2, out2, err2 = self.run_cli("token")
        self.assertEqual(code2, 0, msg=err2)
        self.assertEqual(out2.strip(), token)

    def test_token_rotate_generates_new_token(self) -> None:
        code, out, err = self.run_cli("token")
        self.assertEqual(code, 0, msg=err)
        token1 = out.strip()

        code_rot, out_rot, err_rot = self.run_cli("token", "--rotate")
        self.assertEqual(code_rot, 0, msg=err_rot)
        token2 = out_rot.strip()
        self.assertNotEqual(token1, token2)

        # Subsequent token call prints rotated token
        code3, out3, err3 = self.run_cli("token")
        self.assertEqual(code3, 0, msg=err3)
        self.assertEqual(out3.strip(), token2)


class RefreshCommandTests(CliCommandTestCase):
    def test_refresh_runs_one_pass_for_every_asset_family(self) -> None:
        code, out, err = self.run_cli("refresh")
        self.assertEqual(code, 0, msg=err)
        self.assertIn("refreshed: skills, slash_commands, mcp, hooks, permissions, agents", out)

        payload = self.run_json("refresh")
        self.assertEqual(
            payload["refreshed"],
            ["skills", "slash_commands", "mcp", "hooks", "permissions", "agents"],
        )

    def test_refresh_sync_all_enables_auto_adopt_across_families(self) -> None:
        payload = self.run_json("refresh", "--sync-all")
        self.assertEqual(payload["syncAll"], True)
        self.assertIn("skills", payload["refreshed"])


class SettingsCommandTests(CliCommandTestCase):
    def test_show_lists_storage_and_harnesses(self) -> None:
        code, out, err = self.run_cli("settings", "show")
        self.assertEqual(code, 0, msg=err)
        self.assertIn("data dir", out)
        self.assertIn("claude", out)

    def test_harness_support_toggle_round_trips(self) -> None:
        code, _, err = self.run_cli("settings", "harness", "cursor", "--disable")
        self.assertEqual(code, 0, msg=err)
        payload = self.run_json("settings", "show")
        cursor = next(item for item in payload["harnesses"] if item["harness"] == "cursor")
        self.assertFalse(cursor["supportEnabled"])

    def test_health_reports_ok(self) -> None:
        payload = self.run_json("health")
        self.assertTrue(payload["ok"])


class AgentCommandTests(CliCommandTestCase):
    def test_create_bind_and_delete_round_trip(self) -> None:
        code, out, err = self.run_cli(
            "agents", "create", "--name", "Release Bot", "--description", "Cuts releases",
            "--prompt", "You cut releases.", "--tool", "Bash",
        )
        self.assertEqual(code, 0, msg=err)
        self.assertIn("release-bot", out)

        code, _, err = self.run_cli("agents", "enable", "release-bot", "--harness", "claude")
        self.assertEqual(code, 0, msg=err)

        detail = self.run_json("agents", "show", "release-bot")
        self.assertEqual(detail["tools"], ["Bash"])
        claude = next(item for item in detail["harnesses"] if item["harness"] == "claude")
        self.assertEqual(claude["state"], "enabled")

        code, _, err = self.run_cli("agents", "delete", "release-bot", "--yes")
        self.assertEqual(code, 0, msg=err)
        listing = self.run_json("agents", "list")
        self.assertEqual(listing["entries"], [])

    def test_prompt_can_come_from_a_file(self) -> None:
        prompt_path = Path(self._tempdir.name) / "prompt.md"
        prompt_path.write_text("From a file.", encoding="utf-8")
        code, _, err = self.run_cli(
            "agents", "create", "--name", "Filed", "--description", "d", "--prompt-file", str(prompt_path)
        )
        self.assertEqual(code, 0, msg=err)
        self.assertEqual(self.run_json("agents", "show", "filed")["prompt"], "From a file.")

    def test_unknown_agent_exits_one_with_a_message(self) -> None:
        code, _, err = self.run_cli("agents", "show", "nope")
        self.assertEqual(code, 1)
        self.assertIn("agent not found: nope", err)

    def test_update_requires_something_to_change(self) -> None:
        self.run_cli("agents", "create", "--name", "Bot", "--description", "d", "--prompt", "p")
        code, _, err = self.run_cli("agents", "update", "bot")
        self.assertEqual(code, 1)
        self.assertIn("nothing to update", err)

    def test_delete_without_yes_refuses_when_not_a_tty(self) -> None:
        self.run_cli("agents", "create", "--name", "Bot", "--description", "d", "--prompt", "p")
        with mock.patch("sys.stdin.isatty", return_value=False):
            code, _, err = self.run_cli("agents", "delete", "bot")
        self.assertEqual(code, 1)
        self.assertIn("--yes", err)
        # Refusing must not have deleted anything.
        self.assertEqual(self.run_json("agents", "show", "bot")["ref"], "bot")

    def test_create_is_recorded_in_the_shared_mutation_journal(self) -> None:
        code, _, err = self.run_cli(
            "agents",
            "create",
            "--name",
            "Audit Bot",
            "--description",
            "safe description",
            "--prompt",
            "secret prompt that must not be journaled",
        )
        self.assertEqual(code, 0, msg=err)

        audit_path = self.spec.xdg_data_home / APP_NAME / "audit.log"
        event = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(event["family"], "agents")
        self.assertEqual(event["operation"], "create")
        self.assertEqual(event["parameters"], {"name": "Audit Bot"})
        self.assertEqual(event["outcome"], "succeeded")
        self.assertIn(str(self.spec.agents_root / "audit-bot.md"), event["targetPaths"])
        self.assertNotIn("secret prompt", json.dumps(event))


class HookCommandTests(CliCommandTestCase):
    def test_create_and_fan_out_to_every_harness(self) -> None:
        code, _, err = self.run_cli(
            "hooks", "create", "--id", "lint-gate", "--event", "post_tool_use",
            "--command", "npm run lint", "--match", "file_write",
        )
        self.assertEqual(code, 0, msg=err)

        code, out, err = self.run_cli("hooks", "set-harnesses", "lint-gate", "--target", "enabled")
        self.assertEqual(code, 0, msg=err)
        self.assertIn("claude", out)

        listing = self.run_json("hooks", "list")
        entry = next(item for item in listing["entries"] if item["id"] == "lint-gate")
        self.assertEqual(entry["enabledStatus"], "enabled")

    def test_unsupported_match_is_rejected_by_the_parser(self) -> None:
        # "Edit" is a Claude tool name, not a category; the store would accept it and
        # the rule would then never bind anywhere.
        with self.assertRaises(SystemExit):
            self.run_cli(
                "hooks", "create", "--id", "x", "--event", "post_tool_use",
                "--command", "c", "--match", "Edit",
            )


class PermissionCommandTests(CliCommandTestCase):
    def test_create_and_bind_reports_unsupported_harnesses(self) -> None:
        code, _, err = self.run_cli(
            "permissions", "create", "--id", "no-force-push", "--decision", "deny",
            "--scope", "shell", "--pattern", "git push --force",
        )
        self.assertEqual(code, 0, msg=err)

        code, out, err = self.run_cli(
            "permissions", "set-harnesses", "no-force-push", "--target", "enabled", "--json"
        )
        payload = json.loads(out)
        self.assertIn("claude", payload["succeeded"])
        # The exit code tracks the API's own ``ok``: a harness that cannot express the
        # rule is a partial result, and a script has to be able to notice it.
        self.assertEqual(code, 0 if payload["ok"] else 1)
        self.assertEqual(err, "", msg="--json keeps stdout clean for jq and says nothing on stderr")

        listing = self.run_json("permissions", "list")
        entry = next(item for item in listing["entries"] if item["id"] == "no-force-push")
        self.assertEqual(entry["spec"]["scope"], "shell")

    def test_unsupported_scope_is_rejected_by_the_parser(self) -> None:
        with self.assertRaises(SystemExit):
            self.run_cli(
                "permissions", "create", "--id", "x", "--decision", "deny", "--scope", "Bash"
            )


class SlashCommandTests(CliCommandTestCase):
    def test_create_syncs_into_the_default_targets(self) -> None:
        code, out, err = self.run_cli(
            "commands", "create", "--name", "deploy", "--description", "Deploy", "--prompt", "Deploy it."
        )
        self.assertEqual(code, 0, msg=err)
        self.assertIn("synced", out)

        payload = self.run_json("commands", "show", "deploy")
        synced = [entry["target"] for entry in payload["syncTargets"] if entry["status"] == "synced"]
        self.assertIn("claude", synced)

        code, _, err = self.run_cli("commands", "delete", "deploy", "--yes")
        self.assertEqual(code, 0, msg=err)
        self.assertEqual(self.run_json("commands", "list")["commands"], [])




class SkillCommandTests(CliCommandTestCase):
    def test_list_is_empty_on_a_fresh_home(self) -> None:
        payload = self.run_json("skills", "list")
        self.assertEqual(payload["summary"]["managed"], 0)
        self.assertEqual(payload["rows"], [])


class McpCommandTests(CliCommandTestCase):
    def test_list_and_unmanaged_are_readable_on_a_fresh_home(self) -> None:
        self.assertEqual(self.run_json("mcp", "list")["entries"], [])
        self.assertEqual(self.run_json("mcp", "unmanaged")["servers"], [])

    def test_adopt_disable_enable_preserves_unknown_entry_fields(self) -> None:
        config_path = self.spec.home / ".claude.json"
        config_path.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "exa": {
                            "type": "stdio",
                            "command": "npx",
                            "args": ["-y", "exa-mcp-server"],
                            "disabled": True,
                            "autoApprove": ["read"],
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        code, _, err = self.run_cli("mcp", "adopt", "exa", "--observed-harness", "claude")
        self.assertEqual(code, 0, msg=err)
        code, _, err = self.run_cli("mcp", "disable", "exa", "--harness", "claude")
        self.assertEqual(code, 0, msg=err)
        code, _, err = self.run_cli("mcp", "enable", "exa", "--harness", "claude")
        self.assertEqual(code, 0, msg=err)

        entry = json.loads(config_path.read_text(encoding="utf-8"))["mcpServers"]["exa"]
        self.assertIs(entry["disabled"], True)
        self.assertEqual(entry["autoApprove"], ["read"])


if __name__ == "__main__":
    unittest.main()
