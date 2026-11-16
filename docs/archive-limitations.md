# Archive limitations

Hooks are not currently offered for archiving. Hook removal in several harness
adapters matches the command across events or matcher groups, so removing one
managed hook can also remove a distinct user hook with the same command. The
canonical hook manifest cannot reconstruct those other entries. Archiving hooks
requires a verified, occurrence-specific removal path before it can safely clear
bindings and recorded intent.

Permissions are not currently offered for archiving. Some permission adapters
remove every matching pattern across allow, deny, and ask lists and across
several scopes; they can also remove surrounding default-policy settings. Those
other user rules and settings are not stored in the managed permission manifest,
so unarchive could not restore them. Safe archiving requires occurrence-specific
ownership and removal of only the managed rule and its owned policy changes.
