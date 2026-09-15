"""
Harness Asset Manager compatibility shim for Hermes.

This file is installed as a sidecar into the Hermes virtualenv's site-packages
along with a .pth file to load it on startup. It patches Hermes internals via
a meta_path hook to properly support skills symlinked by Harness Asset Manager.
"""

import sys
import importlib.abc

__version__ = "0.1.0"

def _patch_skill_usage(module):
    try:
        from pathlib import Path
        from agent.skill_utils import is_external_skill_path, iter_skill_index_files

        def _iter_skill_mds(base, *, local_only):
            for skill_md in iter_skill_index_files(Path(base), "SKILL.md"):
                if local_only and is_external_skill_path(skill_md):
                    continue
                yield module._read_skill_name(skill_md, fallback=skill_md.parent.name), skill_md

        module._iter_skill_mds = _iter_skill_mds
    except Exception:
        pass


def _patch_skill_manager_tool(module):
    try:
        from pathlib import Path
        from agent.skill_utils import get_all_skills_dirs, iter_skill_index_files

        def _iter_skill_dirs(root):
            # iter_skill_index_files already prunes EXCLUDED_SKILL_DIRS and skill support dirs,
            # so the old is_excluded_skill_path filter is redundant — dropping it is correct.
            for skill_md in iter_skill_index_files(Path(root), "SKILL.md"):
                yield skill_md.parent

        def _find_skill(name):
            # LEXICAL match against the unresolved local root: resolving a child
            # directory symlink destroys the `harnessam/<skill>` identity.
            local_root = module._skills_dir() if ("/" in name or "\\" in name) else None
            for skills_dir in get_all_skills_dirs():
                if not skills_dir.exists():
                    continue
                for skill_dir in _iter_skill_dirs(skills_dir):
                    if skill_dir.name == name:
                        return {"path": skill_dir}
                    if local_root is not None:
                        try:
                            relative = skill_dir.relative_to(local_root)
                        except ValueError:
                            continue
                        if relative.as_posix() == name:
                            return {"path": skill_dir}
            return None

        module._iter_skill_dirs = _iter_skill_dirs
        module._find_skill = _find_skill
    except Exception:
        pass


def _patch_skills_tool(module):
    """Stop a directory-symlinked package tripping the trusted-directory warning.

    ``_log_security_warnings`` asks ``_under_any``, which compares only the
    *resolved* path. A package that is a directory symlink resolves outside the
    skills root, so a skill sitting exactly where it belongs gets warned about --
    noise a native package never produces.

    Patch the warning function ONLY. ``_under_any`` itself also backs the
    project-skill quarantine gate and ``_collect_skill_candidates``; relaxing it
    globally would weaken a real security control. Trust is decided by the
    lexical path being under a trusted root -- the same root the skill was
    discovered through -- never by pattern-matching a path string.
    """
    try:
        from contextlib import suppress

        injection_patterns = module._INJECTION_PATTERNS
        logger = module.logger

        def _log_security_warnings(name, skill_md, content, all_dirs, active_skills_dir):
            lexically_trusted = any(
                skill_md.is_relative_to(d) for d in (active_skills_dir, *all_dirs)
            )
            resolved_trusted = [active_skills_dir.resolve()]
            with suppress(Exception):
                resolved_trusted.extend(d.resolve() for d in all_dirs)
            warnings = []
            if not lexically_trusted and not module._under_any(skill_md, resolved_trusted):
                warnings.append(
                    "skill file is outside the trusted skills directory "
                    f"(~/.hermes/skills/): {skill_md}"
                )
            if any(p in content.lower() for p in injection_patterns):
                warnings.append("skill content contains patterns that may indicate prompt injection")
            if warnings:
                logger.warning("Skill security warning for '%s': %s", name, "; ".join(warnings))

        module._log_security_warnings = _log_security_warnings
    except Exception:
        pass


class _PatchedLoader:
    def __init__(self, inner, patch):
        self._inner = inner
        self._patch = patch

    def exec_module(self, module):
        self._inner.exec_module(module)
        self._patch(module)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _PatchingFinder(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.patches = {
            "tools.skill_usage": _patch_skill_usage,
            "tools.skill_manager_tool": _patch_skill_manager_tool,
            "tools.skills_tool": _patch_skills_tool,
        }
        self._is_handling = set()

    def find_spec(self, fullname, path, target=None):
        if fullname in self.patches and fullname not in self._is_handling:
            self._is_handling.add(fullname)
            try:
                for finder in sys.meta_path:
                    if finder is self:
                        continue
                    if hasattr(finder, 'find_spec'):
                        spec = finder.find_spec(fullname, path, target)
                        if spec is not None and spec.loader is not None:
                            spec.loader = _PatchedLoader(spec.loader, self.patches[fullname])
                            return spec
            finally:
                self._is_handling.remove(fullname)
        return None

def install_hook():
    for finder in sys.meta_path:
        if isinstance(finder, _PatchingFinder):
            return # Idempotent: already installed

    sys.meta_path.insert(0, _PatchingFinder())

install_hook()
