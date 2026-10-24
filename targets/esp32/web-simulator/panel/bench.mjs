import "./components/twatch-2020.mjs";
const watch = document.querySelector("gar-twatch-2020");
const ctx = watch.displayContext;
ctx.fillStyle = "#10261d";
ctx.fillRect(0, 0, 240, 240);
ctx.strokeStyle = "#355447";
for (let p = 0; p < 240; p += 24) {
  ctx.beginPath();
  ctx.moveTo(p, 0);
  ctx.lineTo(p, 240);
  ctx.moveTo(0, p);
  ctx.lineTo(240, p);
  ctx.stroke();
}
ctx.fillStyle = "#c6f0d8";
ctx.font = "bold 22px system-ui";
ctx.fillText("T-WATCH", 54, 112);
ctx.font = "12px system-ui";
ctx.fillText("240 × 240 / V3", 77, 140);
for (const type of ["gar-touch", "gar-button", "gar-hardware-change"]) {
  watch.addEventListener(
    type,
    ({ detail }) =>
      (document.querySelector("pre").textContent =
        `${type}\n${JSON.stringify(detail, null, 2)}`),
  );
}
document
  .querySelector("input")
  .addEventListener("input", (e) => (watch.brightness = e.target.value));
