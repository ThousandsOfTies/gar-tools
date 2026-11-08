# Existing-release script updates

This provider updates a Product-declared set of Node library files while keeping
the existing native executables, wiring, launch files and private configuration.
It is a script-update artifact, not a complete native firmware build.

Bind it from `gar-target-update.json`. The Product owns file selection, service,
architecture, deployment root and SSH identity. Run each phase explicitly:

```
gar target update --workspace Local/Product --phase build --json
gar target update --workspace Local/Product --phase preflight --json
gar target update --workspace Local/Product --phase deploy --json
gar target update --workspace Local/Product --phase diag --json
```

Build writes an immutable content-addressed snapshot under `.gar/runtime-updates`.
It records updated-file hashes and source commits; deployment refuses snapshots
whose updated files had uncommitted changes. Preflight reads actual release/file
hashes, architecture, service state and the binding to the active symlink. It
does not stop or change the App.

Deploy requires Linux administrator authentication in the masked local form.
It rechecks the preflight hashes before cloning the previous release, applies
only `.cjs`/`.mjs`/`.js` files, runs Node syntax checks, switches the App symlink
and restarts that service. Optional `validateImports` imports the declared
library modules as the non-root service user before activation; use it only for
modules that have no top-level device side effects. A failed restart restores
the previous release. Old and failed releases are retained for diagnosis.
Secrets never enter the artifact or command arguments. Public source payloads
are read from the local snapshot and sent over SSH stdin after authentication.

Diag compares the active release receipt, all changed-file hashes and service
state to the expected build ID. Deployment also requires a different live PID.
This establishes the selected service's update, not cloud authentication,
acoustic quality or a full hardware test; those need Product probes and a user
interaction on the actual device.

`python test_update.py` covers corrupted artifacts, traversal/non-script paths,
changed preflight hashes, syntax rejection, preservation of native/private files
and rollback. On Windows the transaction tests substitute only symlink switching
and service calls; physical activation still needs Linux verification.
