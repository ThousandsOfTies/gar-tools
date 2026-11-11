# Headless Gemini Live credentials

`broker.cjs` is an App-independent Node.js 22+ HTTPS client. It does not open an
audio device, choose robot behavior, retain provider tokens on disk or log
credentials. Products supply their private device profile and the shared API URL.

```js
const {loadProfile, requestToken} = require('./broker.cjs');
const connection = await requestToken(loadProfile('/private/device.json'), {signal});
await geminiLive.connect({...connection, voice, instruction, tools});
```

Profile fields: `url` (HTTPS `/api/live/token`), `deviceId`, `secret` (32 random
bytes encoded as base64url). Linux profiles must be regular owner-private files,
mode 0600. Provision them separately from public Product bundles. The matching
API stores SHA-256 device credential hashes and its own Gemini API key.

The client refuses redirects and expired/unbounded credentials. Requests have a
15-second timeout and responses are capped at 16 KB. Its result includes
`ephemeralToken`, `model`, `apiVersion`, `expiresAt`; keep it in memory only.
The shared `web-simulator/components/gemini-live.mjs` protocol accepts either a
direct API key or an ephemeral token and selects the constrained WebSocket
endpoint for tokens. Renewal, retries and microphone state belong to the App.

Independent verification, including two differently configured devices:

```sh
node --test targets/linux-device/runtime/gemini-live/broker.test.cjs web-simulator/tests/audio-live.test.mjs
```

Current server implementation is the existing `home-teacher-api` project's
`src/liveTokens.ts`; see its `LIVE_TOKENS.md` for provisioning and limits.
