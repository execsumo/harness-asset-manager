import re
with open("harness_asset_manager/application/configs/service.py", "r") as f:
    code = f.read()

restore_old = '''    def restore(self, harness: str) -> None:
        """Restore preferences from manifest to the local file."""
        manifest = self.store.load()
        record = manifest.configs.get(harness)
        if not record:
            return

        profile = self._get_binding_profile(harness)
        if not profile:
            return'''
            
restore_new = '''    def restore(self, harness: str) -> None:
        """Restore preferences from manifest to the local file."""
        manifest = self.store.load()
        record = manifest.configs.get(harness)
        if not record:
            return

        profile = self._get_binding_profile(harness)
        if not profile:
            return
            
        if profile.file_format in {"toml", "jsonc"}:
            raise ValueError(f"Cannot restore {profile.file_format} files without rewriting unowned content or stripping comments. Restore refused.")'''

code = code.replace(restore_old, restore_new)
with open("harness_asset_manager/application/configs/service.py", "w") as f:
    f.write(code)
