# Archive limitations

Hooks are not currently offered for archiving. Hook removal in several harness
adapters matches the command across events or matcher groups, so removing one
managed hook can also remove a distinct user hook with the same command. The
canonical hook manifest cannot reconstruct those other entries. Archiving hooks
requires a verified, occurrence-specific removal path before it can safely clear
bindings and recorded intent.
