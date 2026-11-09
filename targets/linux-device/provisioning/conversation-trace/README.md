# Temporary Node conversation observation

This provider attaches to an existing systemd-managed Node process for at most
60 seconds. It does not deploy an App, restart its service or record audio.
The Product binds the service, Node executable, entrypoint, runtime module and
prototype export. An App-owned function defines the observation and restores
its own temporary handlers. `observe.cjs` provides only the inspector RPC path.

The root recipe refuses an existing inspector listener, enables a loopback-only
inspector with SIGUSR1, and transfers an opaque array of instances to the
App observer. Module properties, credentials and heap contents are not dumped.
The App observer must return counts and events without payloads, restore its
handlers within the duration, and leave the original conversation running.
The inspector is closed after the result or a normal observer failure.

Declare the entrypoint in the Product's `gar-operations.json` and run it through
`gar product run trace`. A Product may retain `gar target trace` as a local alias.
The Linux password is entered only into the local masked setup form and sent
over SSH stdin when sudo requests it. No password is saved.

Validation: `node --test observe.test.cjs` exercises a real child-process Node
inspector with a fixture prototype and injected observer, verifies restoration,
and checks that fixture payloads do not appear in the result. App observation
semantics must also be tested in the App repository. A physical trace establishes
actual ordering for that interval; it does not establish causality or prove a fix.
