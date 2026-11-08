import "./gar-components/controls.mjs";
import "./gar-components/event-log.mjs";
import "./gar-components/connection-status.mjs";
import "./gar-components/rotary.mjs";
import "./gar-components/camera-input.mjs";

const results = document.querySelector("#results");
const fixture = document.querySelector("#fixture");
const lines = [];
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const run = (name, test) => {
  try { test(); lines.push(`PASS - ${name}`); }
  catch (error) { lines.push(`FAIL - ${name}: ${error.message}`); }
  results.textContent = lines.join("\n");
};
const schema = [
  { id: "level", type: "range", label: "Level", value: 40, min: 0, max: 100, step: 5, unit: "%" },
  { id: "enabled", type: "checkbox", label: "Enabled", value: true },
  { id: "mode", type: "select", label: "Mode", value: "a", options: [{ value: "a", label: "Alpha" }, { value: "b", label: "Beta" }] },
  { id: "reset", type: "action", label: "Reset" },
];
const controls = document.createElement("gar-sim-controls");
const other = document.createElement("gar-sim-controls");
controls.schema = schema;
other.schema = schema;
fixture.append(controls, other);
const input = (id) => [...controls.shadowRoot.querySelectorAll("[data-control-id]")].find((element) => element.dataset.controlId === id);
const events = [];
fixture.addEventListener("gar-control", (event) => events.push(event));

run("schema creates accessible native inputs with independent state", () => {
  assert(input("level").labels.length === 1 && input("level").labels[0].textContent.includes("Level"), "range label");
  assert(input("level").labels[0].control === input("level"), "label must target the range, not its value readout");
  assert(input("enabled").labels.length === 1 && input("mode").labels.length === 1, "native labels");
  assert(input("reset").textContent === "Reset", "action name");
  assert(controls.values.level === 40 && controls.values.enabled && controls.values.mode === "a", "initial values");
  controls.values = { level: 62, mode: "b" };
  assert(controls.values.level === 60 && other.values.level === 40 && other.values.mode === "a", "normalized independent values");
  assert(events.length === 0, "programmatic updates must stay silent");
});

run("range, checkbox, select and action emit typed composed events once", () => {
  events.length = 0;
  input("level").value = "75";
  input("level").dispatchEvent(new Event("input", { bubbles: true }));
  input("level").dispatchEvent(new Event("change", { bubbles: true }));
  input("enabled").click();
  input("mode").value = "b";
  input("mode").dispatchEvent(new Event("change", { bubbles: true }));
  input("reset").click();
  assert(events.length === 4, `event count ${events.length}`);
  assert(events.every((event) => event.bubbles && event.composed), "public event flags");
  assert(JSON.stringify(events.map((event) => event.detail)) === JSON.stringify([
    { id: "level", value: 75 }, { id: "enabled", value: false },
    { id: "mode", value: "b" }, { id: "reset", value: true },
  ]), "typed event payloads");
});

run("disabling controls suppresses events; reconnect keeps one listener", () => {
  events.length = 0;
  controls.disabled = true;
  assert(input("level").matches(":disabled"), "native disabled semantics");
  input("reset").click();
  input("level").dispatchEvent(new Event("input", { bubbles: true }));
  controls.values = { level: 25 };
  assert(events.length === 0 && controls.values.level === 25, "disabled and programmatic updates");
  controls.disabled = false;
  for (let i = 0; i < 3; i++) { controls.remove(); fixture.append(controls); }
  input("reset").click();
  assert(events.length === 1, "reconnect duplicated handlers");
});

run("schema replacement is isolated, text-safe, and validates before changing UI", () => {
  events.length = 0;
  const changed = controls.schema;
  changed[0].label = "<img src=x onerror=alert(1)>";
  changed[3].disabled = true;
  controls.schema = changed;
  assert(!controls.shadowRoot.querySelector("img"), "label interpreted as HTML");
  assert(other.schema[0].label === "Level", "shared schema mutation");
  input("reset").click();
  assert(events.length === 0, "disabled action");
  let rejected = false;
  try { controls.schema = [{ id: "same", type: "range" }, { id: "same", type: "action" }]; }
  catch { rejected = true; }
  assert(rejected && controls.schema.length === 4, "atomic duplicate validation");
  controls.schema = schema;
  input("reset").click();
  assert(events.length === 1, "schema replacement event count");
});

const log = document.createElement("gar-event-log");
const secondLog = document.createElement("gar-event-log");
fixture.append(log, secondLog);
run("event history is bounded, keeps order and renders untrusted data as text", () => {
  log.maxEntries = 3;
  for (const line of ["first", "second", "third", "<img src=x onerror=alert(1)>"]) log.append(line);
  const entries = [...log.shadowRoot.querySelectorAll("li")].map((entry) => entry.textContent);
  assert(log.count === 3 && entries[0] === "second" && entries[2].startsWith("<img"), "bounded FIFO order");
  assert(!log.shadowRoot.querySelector("img") && secondLog.count === 0, "text safety and isolation");
  log.maxEntries = 1;
  assert(log.count === 1 && log.shadowRoot.querySelector("li").textContent.startsWith("<img"), "lowering limit trims immediately");
});

run("log labels, empty state, clear button and reconnect work independently", () => {
  log.label = "Messages";
  log.clearLabel = "Erase";
  log.emptyLabel = "Waiting for input";
  assert(log.shadowRoot.querySelector("h2").textContent === "Messages", "heading label");
  assert(log.shadowRoot.querySelector("button").textContent === "Erase", "button label");
  assert(log.shadowRoot.querySelector('[role="log"]').getAttribute("aria-live") === "polite", "accessible log");
  log.remove(); fixture.append(log);
  log.shadowRoot.querySelector("button").click();
  assert(log.count === 0 && log.shadowRoot.querySelector("button").disabled, "clear button");
  assert(!log.shadowRoot.querySelector("p").hidden && log.shadowRoot.querySelector("p").textContent === "Waiting for input", "empty label");
  log.append("after reconnect");
  assert(log.count === 1, "append after reconnect");
  log.clear();
  assert(log.count === 0 && secondLog.label === "Events", "clear and instance isolation");
});

run("invalid limits fall back to the documented bound", () => {
  for (const limit of [0, -1, "invalid", Infinity]) {
    log.maxEntries = limit;
    assert(log.maxEntries === 200, `invalid bound ${limit}`);
  }
  log.maxEntries = 2.9;
  assert(log.maxEntries === 2, "integer bound");
});

const rotary = document.createElement("gar-rotary");
const status = document.createElement("gar-connection-status");
const camera = document.createElement("gar-camera-input");
camera.endpoint = "/camera-input/ws";
fixture.append(rotary, status, camera);
run("rotary input emits portable events and reconnect keeps one listener", () => {
  const events = [];
  rotary.addEventListener("gar-rotary-input", ({ detail }) => events.push(detail));
  const plus = rotary.shadowRoot.querySelector('[data-direction="1"]');
  plus.click();
  rotary.remove(); fixture.append(rotary); rotary.shadowRoot.querySelector('[data-press]').click();
  assert(JSON.stringify(events) === JSON.stringify([{ type: "rotate", direction: 1 }, { type: "press" }]), "rotary events");
});

run("connection status consumes an injected source without owning transport", () => {
  const source = new EventTarget();
  source.connected = false;
  status.source = source;
  assert(status.dataset.connected === "false", "initial disconnected status");
  source.dispatchEvent(new CustomEvent("connection", { detail: { connected: true } }));
  assert(status.dataset.connected === "true" && status.shadowRoot.querySelector("span").textContent.includes("Connected"), "connected status");
  assert(status.shadowRoot.querySelector("span").textContent.includes("Connected"), "source controls status only");
});

run("camera input keeps device controls and preview inside its shadow DOM", () => {
  assert(camera.shadowRoot.querySelector("video"), "camera preview is encapsulated");
  assert(camera.shadowRoot.querySelector("select") && camera.shadowRoot.querySelector("button"), "camera controls");
  assert(!camera.querySelector("video") && camera.endpoint === "/camera-input/ws", "portable endpoint contract");
});

const passed = lines.filter((line) => line.startsWith("PASS")).length;
results.textContent += `\n\n${passed}/${lines.length} passed`;
document.title = `${passed === lines.length ? "PASS" : "FAIL"} - Shared simulator tests`;
document.documentElement.dataset.testResult = passed === lines.length ? "pass" : "fail";
