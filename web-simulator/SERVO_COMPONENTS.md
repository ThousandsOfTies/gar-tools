# Reusable PWM and input parts

The implementation lives in `components/`; Products keep only wiring, calibration,
motion mappings and presentation. No framework or npm build is required.

Run a Product-independent, two-controller example from the gar-tools root:

```sh
python web-simulator/serve.py --panel web-simulator/examples/pwm-parts --port 8766
node --test web-simulator/tests/servo-components.test.mjs
```

The example deliberately uses two different I2C addresses and servo channels 2
and 11. Each controller selects its own telemetry, and each servo subscribes to
the controller referenced by its `controller-id` attribute. No four-servo robot
layout or motion sequence is built into the parts.

| Part | Contract |
| --- | --- |
| `pca9685.js` / `<gar-pca9685>` | Set `.transport` to an `EventTarget` exposing `.state` and `message` events with `event.detail`. Optional `device` and `address` select a controller. `.state` exposes its normalized state and `gar-pca9685-state` emits changes. |
| `sg90.js` / `<gar-sg90>` | Give it an `id`, `controller-id` referencing a PCA9685 in the same document/shadow root, and `channel` from 0 to 15. `min-pulse-us` and `max-pulse-us` configure the preview calibration. Connect the controller before the servo. |
| `gamepad.js` / `<gar-gamepad>` | Emits `gar-gamepad-input` with axes, button or stop input plus its source. Physical input also includes `pressedButtons`, the simultaneously held A/B/X/Y names. Product listeners choose actions and may call `cancel()` to discard the remaining sample and require neutral before rearming. B has no fixed action. Labels use `button-a-label`, etc.; `disabled` stops input. The widget sends no network commands. |
| `servo-model.mjs` | Pure PWM normalization, pulse conversion and angle estimation; also usable from Node. |
| `gamepad-model.mjs` | Pure standard gamepad sampling and deadzone handling. |
| `telemetry-transport.mjs` | Read-only WebSocket subscription, reconnect and local preview state. Accepts `url`, `initialState`, `reduceMessage` and `retryMs` options. |

PCA9685 accepts the existing bridge messages (`init.state.i2c.pca9685` and
`type: "pca9685"`). An initial snapshot may also carry an array of controller
states for multiple boards. A missing `device` in legacy telemetry matches a
selector by address; explicit device values are checked when supplied. Multiple
controllers with identical addresses need separate transports or explicit device
identities in their telemetry.

```js
import './gar-components/pca9685.js';
import './gar-components/sg90.js';
import { TelemetryTransport } from './gar-components/telemetry-transport.mjs';

const source = new TelemetryTransport();
document.querySelector('gar-pca9685').transport = source;
source.select('live'); // Default same-origin /ws; only subscribes.
// source.select('demo'); source.publish({ i2c: { pca9685: yourState } });
// source.close(); // Explicitly dispose the subscription when the page is removed.
```

PCA9685, SG90 and the gamepad keep their implementation and default CSS in their
own Shadow DOM. Product HTML only declares physical identity and connections.
Use `appearance="compact"` on SG90 or `appearance="channels"` on PCA9685 for the
built-in alternate presentations. Theme only through the documented inherited
custom properties: `--gar-component-accent`, `--gar-component-border`,
`--gar-component-panel`, `--gar-component-text`, `--gar-component-muted`,
`--gar-component-reading`, `--gar-servo-body`, `--gar-servo-ear`, and
`--gar-servo-edge`. Product selectors cannot depend on internal class names.

The common static server and Linux web bridge expose `/gar-components/`. Source
checkouts resolve the common directory automatically; an installed Linux bridge
uses a sibling `gar-components/` package, `/usr/local/share/gar/web-simulator/components`,
or an explicit `GAR_WEB_COMPONENTS_DIR`.
Runtime packages must include this directory. Product builds and VM archives must
use the same pinned gar-tools checkout as the panel.

GarServoPet variants demonstrate thin compatibility re-exports with an HTML import
map: Node resolves the real `sources/gar-tools` modules, while the browser maps
them to the common URL. Their four-servo demo and VM command mapping remain in
the Product.

Both PCA9685 appearances retain the board and terminals. Compact SG90 retains its
controller/channel route. Products should keep these parts visible alongside their
application controls, including when detailed telemetry is collapsed.
