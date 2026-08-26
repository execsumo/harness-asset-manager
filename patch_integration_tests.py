import re
with open("tests/integration/test_configs_api.py", "r") as f:
    code = f.read()

code = code.replace(
    '''            res = harness.post_raw("/api/configs/codex/restore")
            self.assertEqual(res.status_code, 400)
            self.assertIn("Cannot restore", res.json()["error"])''',
    '''            res = harness.post_json("/api/configs/codex/restore", expected_status=400)
            self.assertIn("Cannot restore", res["error"])'''
)

with open("tests/integration/test_configs_api.py", "w") as f:
    f.write(code)
