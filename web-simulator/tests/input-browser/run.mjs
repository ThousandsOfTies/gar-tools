import './gar-components/rotary.mjs';
import './gar-components/gamepad.js';
const fixture = document.getElementById('fixture');
const results = document.getElementById('results');
const lines = [];
const check = (condition, message) => { if (!condition) throw new Error(message); };
async function run(name, test) {
  try { await test(); lines.push(`PASS ${name}`); }
  catch (error) { lines.push(`FAIL ${name}: ${error.message}`); }
  results.textContent = lines.join('\n');
}
const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
fixture.innerHTML = '<gar-rotary id="first" steps-per-turn="20"></gar-rotary><gar-rotary id="second" steps-per-turn="40" value="5"></gar-rotary><gar-gamepad id="pad-a"></gar-gamepad><gar-gamepad id="pad-b" button-b-label="Alternate"></gar-gamepad>';
const first = document.getElementById('first');
const second = document.getElementById('second');
const firstEvents = [];
first.addEventListener('gar-rotary-input', event => {
  firstEvents.push(event);
  if (event.detail.type === 'rotate') first.value += event.detail.direction;
});
const knob = first.shadowRoot.querySelector('.knob');
await run('two encoders retain independent counters and visible rotating markers', () => {
  first.shadowRoot.querySelector('[data-direction="1"]').click();
  check(first.value === 1 && second.value === 5, 'independent counter state');
  check(first.shadowRoot.querySelector('.dial').style.transform === 'rotate(18deg)', '20-step marker');
  check(second.shadowRoot.querySelector('.dial').style.transform === 'rotate(45deg)', '40-step marker');
  check(knob.getBoundingClientRect().width > 40 && getComputedStyle(first.shadowRoot.querySelector('.dial'), '::before').content !== 'none', 'visible knob and marker');
  check(firstEvents[0].bubbles && firstEvents[0].composed, 'portable public input');
});
await run('arrow keys rotate; knob click and PRESS each emit one press', () => {
  knob.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', cancelable: true }));
  knob.click(); first.shadowRoot.querySelector('[data-press]').click();
  check(first.value === 2, 'arrow step');
  check(firstEvents.filter(event => event.detail.type === 'press').length === 2, 'one press per click');
});
await run('wheel keeps page scrolling until focused and does not consume zoom', () => {
  const wheel = options => new WheelEvent('wheel', { deltaY: -40, cancelable: true, ...options });
  knob.blur();
  let event = wheel(); knob.dispatchEvent(event);
  check(!event.defaultPrevented && first.value === 2, 'unfocused wheel');
  knob.focus(); event = wheel(); knob.dispatchEvent(event);
  check(event.defaultPrevented && first.value === 3, 'focused wheel step');
  event = wheel({ ctrlKey: true }); knob.dispatchEvent(event);
  check(!event.defaultPrevented && first.value === 3, 'zoom gesture');
  knob.blur();
});
await run('disabled and reconnect preserve single-event input behavior', () => {
  const count = firstEvents.length;
  first.disabled = true;
  knob.click(); knob.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
  check(firstEvents.length === count, 'disabled events');
  first.disabled = false;
  first.remove(); fixture.prepend(first);
  first.shadowRoot.querySelector('[data-direction="-1"]').click();
  check(firstEvents.length === count + 1 && first.value === 2, 'reconnect listener isolation');
});
const padA = document.getElementById('pad-a');
const padB = document.getElementById('pad-b');
const inputsA = [], inputsB = [];
padA.addEventListener('gar-gamepad-input', event => inputsA.push(event.detail));
padB.addEventListener('gar-gamepad-input', event => inputsB.push(event.detail));
await run('screen B is ordinary input and independent of the other instance', () => {
  padA.reader.ready = true;
  padA.shadowRoot.querySelector('[data-button="b"]').click();
  check(padA.reader.ready && inputsA.at(-1).button === 'b' && inputsB.length === 0, 'B has no implicit cancel');
  check(padB.shadowRoot.querySelector('[data-button="b"]').textContent.includes('Alternate'), 'per-instance label');
});
await run('physical input stays generic; a consumer may cancel the rest of its own sample', async () => {
  const original = Object.getOwnPropertyDescriptor(navigator, 'getGamepads');
  let axes = [0, 0], buttons = [];
  Object.defineProperty(navigator, 'getGamepads', { configurable: true, value: () => [{
    connected: true, mapping: 'standard', index: 0, id: 'test pad', axes,
    buttons: Array.from({length: 16}, (_, i) => ({pressed: buttons.includes(i)})),
  }] });
  const cancelB = ({detail}) => { if (detail.pressedButtons?.includes('b')) padB.cancel(); };
  padB.addEventListener('gar-gamepad-input', cancelB);
  try {
    padA.shadowRoot.querySelector('input').click(); padB.shadowRoot.querySelector('input').click();
    await frame(); await frame();
    inputsA.length = inputsB.length = 0;
    axes = [1, 0]; buttons = [0, 1, 2];
    await frame(); await frame();
    check(inputsA.some(input => input.button === 'b') && inputsA.some(input => input.type === 'axes'), 'B preserves axes');
    check(padA.reader.ready, 'ordinary pad remains armed');
    check(inputsB.length === 1 && !padB.reader.ready, 'consumer cancellation discards remaining simultaneous events');
    buttons = []; axes = [.5, 0]; await frame(); await frame();
    check(inputsB.length === 1, 'cancelled input awaits neutral');
    axes = [0, 0]; await frame(); await frame();
    check(padB.reader.ready, 'neutral rearms the cancelled instance');
  } finally {
    padB.removeEventListener('gar-gamepad-input', cancelB);
    padA.setAttribute('disabled', ''); padB.setAttribute('disabled', '');
    if (original) Object.defineProperty(navigator, 'getGamepads', original);
    else delete navigator.getGamepads;
  }
});
const passed = lines.every(line => line.startsWith('PASS'));
results.textContent += `\n\n${lines.filter(line => line.startsWith('PASS')).length}/${lines.length} passed`;
document.documentElement.dataset.testResult = passed ? 'pass' : 'fail';
document.title = `${passed ? 'PASS' : 'FAIL'} - Input component tests`;
