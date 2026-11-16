# Archive limitations

Hooks and permissions are not currently offered for archiving. Archiving needs
enable and removal to touch only the entries Harness Asset Manager owns, so that
unarchive can put back exactly what was removed. Both families now meet that bar
on enable and disable (below), but the archive path itself has not been built
or verified for them yet.

## What enable and disable guarantee

### Hooks

- **Enable writes one occurrence.** It writes the managed hook under the one
  native event (and matcher group) its record maps to. If that event already holds
  the managed hook, enable replaces it in place, which repairs drift. Enable never
  reads, moves, or removes entries under other events. A user hook with the same
  command under another event, matcher, or OpenCode glob is left alone.
- **Moving a hook is explicit.** When a reconcile from a harness changes the
  hook's event, matcher, or command, the old occurrence is removed by the managed
  record that located it, then the new one is written. Look-alikes are never
  touched.
- **Disable removes one occurrence.** See PR #152: only the occurrence the app
  wrote or adopted is removed.
- **Ambiguity is refused.** If the target event holds the managed command more
  than once (Cursor, OpenCode), or a tagged id appears in several places (Claude,
  Codex), enable and disable fail with a 409 and leave the file unchanged.

### Permissions

- **Enable adds the managed rule and nothing else.** The user's `allow`, `ask`,
  and other `deny` rules are kept, including ones with the same pattern.
- **Enable never overwrites a default policy the user set.** Claude
  `permissions.defaultMode`, Antigravity `toolPermission`, Cursor `approvalMode`,
  and Codex `default_permissions` / `approval_policy` are written only when they
  are unset. Codex `approval_policy` is written only together with
  `default_permissions`, so prompts are never turned off while the user's own
  profile is active.
- **Ownership is recorded, not guessed.** At enable, the app records per harness
  what each of those settings held before and what it wrote, in
  `permissions/default-policy.json` next to the permissions manifest (not in the
  harness config). When the last deny rule leaves the file, disable restores
  exactly the recorded state: a setting the app wrote is removed, unless the user
  has changed it since. A setting the user already had is never touched, even when
  it equals the app's value. The record is cleared at that point.
- **Disable removes only the managed rule.** See PR #152.

## Known limits

- **Codex filesystem rules share one key.** Codex keys filesystem rules by path
  only, and `"deny"` there blocks both reads and writes. A `file_read` and a
  `file_write` permission with the same pattern therefore write the same key, both
  read as enabled once either is, and disabling one removes the key for both.
  Telling them apart would need either a marker in `config.toml`, which Codex
  does not define, or app-side reference counting, which would show a disabled
  permission as still enabled. This is left as is.
- **Owned defaults outlive the app's last rule while user rules remain.** The
  default is released when the deny list is empty (Claude, Antigravity, Cursor)
  or the app's Codex profile is gone. A user deny rule in the same list keeps the
  app's default in place after the app's last rule is disabled.
- **Re-enable re-applies a default the app introduced.** If the app wrote a
  default and the user later changed it, enabling again sets it back. Defaults the
  user had before the app's first write are never overwritten.
- **Codex with a user profile.** When `default_permissions` already names the
  user's own profile, the app's rules are written to its own profile, which Codex
  does not activate, so they have no effect there.
- **Cursor document defaults.** Enable adds `version` and `editor.vimMode` to
  `cli-config.json` when they are missing (`setdefault`), and disable leaves them.
- **State from before ownership was recorded.** For bindings enabled by an older
  version, there is no record. The first enable next to such a rule treats a
  default equal to the app's value as the app's (older versions always wrote it).
  A disable with no record falls back to the earlier rule: remove the default
  when it still holds the app's value.
