import './gar-components/display.mjs';
import './gar-components/controls.mjs';
import './gar-components/event-log.mjs';

const events = document.querySelector('#events');
const examples = [
  { display: '#wide', controls: '#sensor', schema: [
    { id: 'value', type: 'range', label: 'センサー値', min: 0, max: 100, value: 42, unit: '%' },
    { id: 'powered', type: 'checkbox', label: '電源', value: true },
  ], draw(ctx, { value }) {
    ctx.fillStyle = '#0d2435'; ctx.fillRect(0, 0, 320, 180);
    ctx.fillStyle = '#6fd6c4'; ctx.font = 'bold 40px system-ui'; ctx.fillText(`${value}%`, 24, 74);
    ctx.fillStyle = '#193e50'; ctx.fillRect(24, 108, 272, 24);
    ctx.fillStyle = '#6fd6c4'; ctx.fillRect(24, 108, 272 * value / 100, 24);
  } },
  { display: '#small', controls: '#status', schema: [
    { id: 'state', type: 'select', label: '状態', value: 'READY', options: [
      { value: 'READY', label: '待機' }, { value: 'BUSY', label: '動作中' }, { value: 'DONE', label: '完了' },
    ] },
    { id: 'brightness', type: 'range', label: '明るさ', min: 0, max: 100, value: 100, unit: '%' },
  ], draw(ctx, { state }) {
    ctx.fillStyle = '#132416'; ctx.fillRect(0, 0, 128, 64);
    ctx.fillStyle = '#b9ef95'; ctx.font = 'bold 18px monospace'; ctx.fillText(state, 16, 38);
  } },
];
for (const example of examples) {
  const display = document.querySelector(example.display);
  const controls = document.querySelector(example.controls);
  controls.schema = example.schema;
  const render = () => {
    const values = controls.values;
    display.powered = values.powered ?? true;
    display.brightness = values.brightness ?? 100;
    example.draw(display.displayContext, values);
  };
  controls.addEventListener('gar-control', ({ detail }) => {
    render(); events.append(`${display.width}×${display.height} · ${detail.id}: ${detail.value}`);
  });
  display.addEventListener('gar-touch', ({ detail }) => events.append(`${display.width}×${display.height} · ${detail.phase} (${detail.x}, ${detail.y})`));
  render();
}
