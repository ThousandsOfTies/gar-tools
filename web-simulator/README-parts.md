## Generic control and log parts

Both components are dependency-free ES modules with Shadow DOM. They contain no
board or application identifiers, transport calls, timers, or mock domain data.
Load them from the server's shared module route (also preserved in static exports):

```html
<gar-sim-controls id="inputs" label="Inputs"></gar-sim-controls>
<gar-event-log id="events" label="Events" max-entries="100"></gar-event-log>
<script type="module">
  import "./gar-components/controls.mjs";
  import "./gar-components/event-log.mjs";
  const inputs = document.querySelector("#inputs");
  const events = document.querySelector("#events");
  inputs.schema = [
    { id: "level", type: "range", label: "Level", min: 0, max: 100, step: 1, value: 50, unit: "%" },
    { id: "enabled", type: "checkbox", label: "Enabled", value: true },
    { id: "mode", type: "select", label: "Mode", options: ["manual", "auto"], value: "manual" },
    { id: "reset", type: "action", label: "Reset" },
  ];
  inputs.addEventListener("gar-control", ({ detail }) => {
    events.append(`${detail.id}: ${detail.value}`);
    // The owning app maps this to its own model or transport.
  });
</script>
```

### `gar-sim-controls`

| API | Behavior |
| --- | --- |
| `schema` | Array of `{id, type, label, value?, disabled?}`; IDs must be unique non-empty strings. Replacing it resets controls to schema defaults. |
| `type: "range"` | Optional `min`, `max`, `step`, `unit`; native range normalization; numeric value. |
| `type: "checkbox"` | Boolean value, default false. |
| `type: "select"` | `options` of strings or `{value, label}` objects; values are strings; defaults to first option. |
| `type: "action"` | Native button; emits `value` from schema or `true` by default; no persistent value. |
| `values` | Snapshot of value controls keyed by ID; assignment merges known IDs without rebuilding controls or emitting events. |
| `disabled` | Boolean property / presence attribute; disables all controls. Per-control `disabled` also works. |
| `label` | Property / attribute for fieldset legend; default `Controls`. |
| `gar-control` | Bubbles and crosses shadow boundaries; detail `{id, value}`. Range emits on `input`, checkbox/select on `change`, action on click. Programmatic writes are silent. |

Schema getters copy entries and select options; callers can safely edit a returned
schema before assigning it. Native input labels and keyboard behavior are retained.
Each instance owns its state and can be removed and reinserted without duplicate events.

### `gar-event-log`

| API | Behavior |
| --- | --- |
| `append(text)` | Adds one oldest-first entry using `textContent`; does not parse HTML. Scrolls to new entries only when already at the bottom. |
| `clear()` | Removes every entry. The built-in clear button calls the same method. |
| `count` | Read-only number of retained entries. |
| `maxEntries` / `max-entries` | Default 200; values ≥1 are rounded down. Invalid values use 200. Reducing the limit trims immediately. |
| `label` / `label` | Heading, default `Events`. |
| `clearLabel` / `clear-label` | Button label, default `Clear`. |
| `emptyLabel` / `empty-label` | Empty-state text, default `No events yet`. |

History uses an accessible `role="log"` with polite announcements. The application
formats timestamps and structured payloads before appending them. `append(text)`
is the component API and intentionally replaces the native `Element.append()` method.

CSS custom properties: `--gar-panel`, `--gar-border`, `--gar-accent`, and (log only)
`--gar-log-height`. Text color and font inherit from the host page.

Browser regression coverage lives in `tests/browser/`; serve that directory as a
panel with the shared simulator server, open its root URL, and expect the page title
`PASS - Shared simulator tests` and `10/10 passed`.

### `gar-rotary`

The knob keeps a visible rotating marker alongside the existing − / + / PRESS
buttons. Click the knob to press it; arrow keys turn it when focused. Wheel input
is accumulated into steps only while the knob is focused, and Ctrl/Meta wheel
zoom is left to the browser. Circular dragging is not required.

- `value`: acknowledged counter from the host/adapter; setting it updates the
  counter and marker silently. Local rotation animates the marker and emits
  `{type: "rotate", direction: -1 | 1}`. The adapter supplies the resulting counter.
- `steps-per-turn`: marker spacing (default 24, range 1–360); this is a visual
  encoder setting, not a claim about a particular board's hardware.
- `disabled`: presence attribute or boolean property suppresses local input.
- `label`, `press-label`: optional labels; defaults identify the encoder and push.
- `gar-rotary-input`: composed, bubbling rotation or `{type: "press"}` event.

See `examples/input-parts/` for two differently configured, independent encoders
and gamepads. Serve `tests/input-browser/` to check input, scrolling, isolation,
and consumer-selected cancellation separately from Product wiring.
