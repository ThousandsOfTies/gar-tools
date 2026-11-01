import "./components/twatch-2020.mjs";
const results = document.querySelector("#results");
const fixture = document.querySelector("#fixture");
const lines = [];
const assert = (value, label) => {
  if (!value) throw new Error(label);
};
const run = async (name, test) => {
  try {
    await test();
    lines.push(`PASS · ${name}`);
  } catch (error) {
    lines.push(`FAIL · ${name}: ${error.message}`);
  }
  results.textContent = lines.join("\n");
};
const watch = document.createElement("gar-twatch-2020");
fixture.append(watch);
const left = watch.shadowRoot.querySelector(".left");
const power = watch.shadowRoot.querySelector(".power");
const keys = (target, type, repeat = false) =>
  target.dispatchEvent(
    new KeyboardEvent(type, { key: " ", bubbles: true, repeat }),
  );
const touches = [];
watch.addEventListener("gar-touch", (e) => touches.push(e.detail));
await run(
  "keyboard gesture emits one start and one end; repeat is ignored",
  () => {
    keys(left, "keydown");
    keys(left, "keydown", true);
    keys(left, "keyup");
    assert(
      touches.length === 2 &&
        touches[0].phase === "start" &&
        touches[1].phase === "end",
      "gesture count",
    );
    assert(touches[0].x === 60 && touches[0].y === 120, "left coordinate");
  },
);
await run(
  "disconnect cancels input and reconnect does not duplicate events",
  () => {
    touches.length = 0;
    keys(left, "keydown");
    watch.remove();
    assert(touches.at(-1).phase === "cancel", "disconnect release");
    fixture.append(watch);
    touches.length = 0;
    keys(left, "keydown");
    keys(left, "keyup");
    assert(touches.length === 2, "duplicate handlers after reconnect");
  },
);
await run("power off cancels input and disables touch", () => {
  touches.length = 0;
  keys(left, "keydown");
  watch.powered = false;
  assert(touches.at(-1).phase === "cancel" && left.disabled, "off must cancel");
  touches.length = 0;
  keys(left, "keydown");
  keys(left, "keyup");
  assert(touches.length === 0, "powered-off touch");
  watch.powered = true;
});
await run("hardware state is clamped and isolated between instances", () => {
  const other = document.createElement("gar-twatch-2020");
  fixture.append(other);
  watch.battery = -10;
  watch.brightness = 500;
  assert(watch.battery === 0 && watch.brightness === 100, "clamp");
  assert(other.battery === 82 && other.brightness === 85, "instance isolation");
  other.remove();
});
await run("RGB565 frame reaches the actual display canvas", () => {
  const bytes = new Uint8Array(115200);
  bytes.set([0xf8, 0]);
  watch.writeFrame(bytes);
  const pixel = watch.displayContext.getImageData(0, 0, 1, 1).data;
  assert(pixel[0] === 255 && pixel[1] === 0 && pixel[2] === 0, "red pixel");
});
await run(
  "six-second power hold switches off without an ordinary release",
  async () => {
    const buttons = [];
    watch.addEventListener("gar-button", (e) => buttons.push(e.detail));
    keys(power, "keydown");
    await new Promise((resolve) => setTimeout(resolve, 6100));
    keys(power, "keyup");
    assert(watch.powered === false, "power hold");
    assert(
      !buttons.some((e) => e.phase === "up" && !e.held),
      "hold must not emit short press",
    );
    watch.powered = true;
  },
);
const screen = document.createElement("section");
screen.slot = "screen";
const control = document.createElement("button");
control.textContent = "Start";
screen.append(control);
await run(
  "slotted DOM controls replace the halves and receive their own clicks",
  async () => {
    touches.length = 0;
    keys(left, "keydown");
    watch.append(screen);
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert(
      touches.at(-1).phase === "cancel",
      "replacing canvas cancels its gesture",
    );
    assert(
      watch.canvas.hidden && left.hidden && left.disabled,
      "canvas input must be absent",
    );
    let clicked = 0;
    control.addEventListener("click", () => clicked++);
    touches.length = 0;
    control.click();
    keys(left, "keydown");
    keys(left, "keyup");
    assert(
      clicked === 1 && touches.length === 0,
      "element click must not become raw touch",
    );
  },
);
await run(
  "slotted display follows brightness and becomes inert while powered off",
  () => {
    watch.brightness = 43;
    assert(watch.elements.style.opacity === "0.43", "DOM brightness");
    watch.powered = false;
    assert(
      watch.elements.inert && !watch.shadowRoot.querySelector(".off").hidden,
      "off blocks DOM input",
    );
    watch.powered = true;
    assert(!watch.elements.inert, "power restores DOM input");
  },
);
await run(
  "removing slotted content restores the raw canvas input",
  async () => {
    screen.remove();
    await new Promise((resolve) => setTimeout(resolve, 0));
    assert(
      !watch.canvas.hidden && !left.hidden && !left.disabled,
      "restore canvas",
    );
    touches.length = 0;
    keys(left, "keydown");
    keys(left, "keyup");
    assert(touches.length === 2, "raw input restored once");
  },
);
results.textContent += `\n\n${lines.filter((line) => line.startsWith("PASS")).length}/${lines.length} passed`;
document.title = lines.some((line) => line.startsWith("FAIL"))
  ? "FAIL · T-Watch tests"
  : "PASS · T-Watch tests";
