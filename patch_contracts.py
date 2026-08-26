import re
with open("harness_asset_manager/harness/contracts.py", "r") as f:
    code = f.read()

code = code.replace(
    'subtree_path: SubtreePath = ()',
    'subtree_path: SubtreePath = ()\n    exclusion_keys: frozenset[str] = frozenset()'
)

with open("harness_asset_manager/harness/contracts.py", "w") as f:
    f.write(code)
