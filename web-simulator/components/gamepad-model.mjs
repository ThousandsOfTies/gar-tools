/** Standard Gamepad API input, independent of robot, DOM and transport. */
export function stick(x, y, deadzone = 0.15) {
  x = Number.isFinite(x) ? Math.max(-1, Math.min(1, x)) : 0;
  y = Number.isFinite(y) ? Math.max(-1, Math.min(1, y)) : 0;
  const magnitude = Math.hypot(x, y);
  if (magnitude <= deadzone) return [0, 0];
  const scale = (Math.min(1, magnitude) - deadzone) / (1 - deadzone) / magnitude;
  return [x * scale, y * scale].map(v => Math.round(v * 100) / 100);
}

export class GamepadReader {
  constructor() { this.reset(); }
  reset() { this.ready = false; this.axes = [0, 0]; this.buttons = [false, false, false, false]; }
  sample(pad) {
    if (!pad?.connected || pad.mapping !== 'standard') {
      const wasReady = this.ready;
      this.reset();
      return wasReady ? [{ type: 'stop' }] : [];
    }
    const buttons = [0, 1, 2, 3].map(i => !!pad.buttons?.[i]?.pressed);
    const dx = Number(!!pad.buttons?.[15]?.pressed) - Number(!!pad.buttons?.[14]?.pressed);
    const dy = Number(!!pad.buttons?.[13]?.pressed) - Number(!!pad.buttons?.[12]?.pressed);
    const axes = dx || dy ? stick(dx, dy, 0) : stick(pad.axes?.[0], pad.axes?.[1]);
    if (!this.ready) {
      this.ready = axes.every(v => v === 0) && buttons.every(v => !v);
      return [];
    }
    const events = [];
    if (axes.some((v, i) => v !== this.axes[i])) events.push({ type: 'axes', axes });
    buttons.forEach((pressed, i) => {
      if (pressed && !this.buttons[i]) events.push({ type: 'button', button: ['a', 'b', 'x', 'y'][i] });
    });
    this.axes = axes;
    this.buttons = buttons;
    return events;
  }
}
