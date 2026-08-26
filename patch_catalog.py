import re

with open("harness_asset_manager/harness/catalog.py", "r") as f:
    code = f.read()

# Replace the configs binding for claude
code = re.sub(
    r'"configs": ConfigSubtreeBindingProfile\(\s*config_path_resolver=lambda context: context\.home / "\.claude\.json",\s*file_format="json",\s*subtree_path=\(\),\s*\),',
    '"configs": ConfigSubtreeBindingProfile(\n                config_path_resolver=lambda context: context.home / ".claude" / "settings.json",\n                file_format="json",\n                subtree_path=(),\n                exclusion_keys=frozenset(["permissions", "hooks", "mcpServers"]),\n            ),',
    code
)

# codex
code = re.sub(
    r'"configs": ConfigSubtreeBindingProfile\(\s*config_path_resolver=lambda context: context\.home / "\.codex" / "config\.toml",\s*file_format="toml",\s*subtree_path=\(\),\s*\),',
    '"configs": ConfigSubtreeBindingProfile(\n                config_path_resolver=lambda context: context.home / ".codex" / "config.toml",\n                file_format="toml",\n                subtree_path=(),\n                exclusion_keys=frozenset(["mcp_servers", "hooks", "permissions", "features"]),\n            ),',
    code
)

# agy
code = re.sub(
    r'"configs": ConfigSubtreeBindingProfile\(\s*config_path_resolver=lambda context: context\.home / "\.gemini" / "antigravity-cli" / "settings\.json",\s*file_format="json",\s*subtree_path=\(\),\s*\),',
    '"configs": ConfigSubtreeBindingProfile(\n                config_path_resolver=lambda context: context.home / ".gemini" / "antigravity-cli" / "settings.json",\n                file_format="json",\n                subtree_path=(),\n                exclusion_keys=frozenset(["permissions", "toolPermission"]),\n            ),',
    code
)

# cursor
code = re.sub(
    r'"configs": ConfigSubtreeBindingProfile\(\s*config_path_resolver=lambda context: context\.home / "\.cursor" / "settings\.json",\s*file_format="json",\s*subtree_path=\(\),\s*\),',
    '"configs": ConfigSubtreeBindingProfile(\n                config_path_resolver=lambda context: context.home / ".cursor" / "cli-config.json",\n                file_format="json",\n                subtree_path=(),\n                exclusion_keys=frozenset(["permissions", "approvalMode"]),\n            ),',
    code
)

# opencode
code = re.sub(
    r'"configs": ConfigSubtreeBindingProfile\(\s*config_path_resolver=lambda context: context\.home / "\.opencode" / "opencode\.jsonc",\s*file_format="jsonc",\s*subtree_path=\(\),\s*\),',
    '"configs": ConfigSubtreeBindingProfile(\n                config_path_resolver=lambda context: context.home / ".opencode" / "opencode.jsonc",\n                file_format="jsonc",\n                subtree_path=(),\n                exclusion_keys=frozenset(["mcpServers", "hooks"]),\n            ),',
    code
)

# droid - remove configs binding entirely
code = re.sub(
    r'\s*"configs": ConfigSubtreeBindingProfile\(\s*config_path_resolver=lambda context: _factory_home\(context\) / "settings\.json",\s*file_format="json",\s*subtree_path=\(\),\s*\),',
    '',
    code
)

# hermes - add exclusion keys
code = re.sub(
    r'"configs": ConfigSubtreeBindingProfile\(\s*config_path_resolver=_hermes_config_path,\s*file_format="yaml",\s*subtree_path=\(\),\s*\),',
    '"configs": ConfigSubtreeBindingProfile(\n                config_path_resolver=_hermes_config_path,\n                file_format="yaml",\n                subtree_path=(),\n                exclusion_keys=frozenset(["mcp_servers"]),\n            ),',
    code
)

with open("harness_asset_manager/harness/catalog.py", "w") as f:
    f.write(code)
