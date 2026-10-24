import './gar-components/pca9685.js';
import './gar-components/sg90.js';
import { TelemetryTransport } from './gar-components/telemetry-transport.mjs';
import { emptyPca9685State } from './gar-components/servo-model.mjs';

const results = document.getElementById('results');
const fixture = document.getElementById('fixture');
const lines = [];
function check(condition, name) {
  if (!condition) throw new Error(name);
  lines.push(`PASS ${name}`);
}
function state(address, channel, pulseUs) {
  const value = emptyPca9685State();
  value.address = address;
  value.frequencyHz = 50;
  value.channels[channel] = { channel, on: 0, off: Math.round(pulseUs * 4096 * 50 / 1e6), fullOn: false, fullOff: false };
  return { i2c: { pca9685: value } };
}
try {
  const first = new TelemetryTransport();
  const second = new TelemetryTransport();
  fixture.innerHTML = '<gar-pca9685 id="board-a" address="0x40"></gar-pca9685><gar-pca9685 id="board-b" address="0x41"></gar-pca9685><gar-sg90 id="servo" controller-id="board-a" channel="2"></gar-sg90>';
  const board = fixture.querySelector('#board-a');
  const other = fixture.querySelector('#board-b');
  const servo = fixture.querySelector('#servo');
  board.transport = first;
  other.transport = second;
  first.publish(state(0x40, 2, 1500));
  second.publish(state(0x41, 2, 2500));
  const angle = element => element.shadowRoot.querySelector('[data-angle]').textContent;
  check(board.childElementCount === 0 && servo.childElementCount === 0,
    'electronic part implementation stays out of Product light DOM');
  check(board.shadowRoot.querySelectorAll('link[rel="stylesheet"]').length === 1
    && servo.shadowRoot.querySelectorAll('link[rel="stylesheet"]').length === 1,
    'each electronic part owns one private stylesheet');
  check(angle(servo) === '90°', 'controller-id selects the first board');
  servo.setAttribute('controller-id', 'board-b');
  check(angle(servo) === '180°', 'controller-id switches to second board');
  first.publish(state(0x40, 2, 500));
  check(angle(servo) === '180°', 'old controller updates are detached');
  servo.setAttribute('controller-id', 'board-a');
  const replacement = new TelemetryTransport({ initialState: () => state(0x40, 2, 1500) });
  board.transport = replacement;
  check(angle(servo) === '90°', 'changing transport adopts its snapshot');
  first.publish(state(0x40, 2, 2500));
  check(angle(servo) === '90°', 'old transport updates are detached');
  board.remove();
  check(!servo.classList.contains('active'), 'disconnecting controller clears attached servo signal');
  replacement.publish(state(0x40, 2, 2500));
  check(!servo.classList.contains('active'), 'detached controller ignores transport updates');
  fixture.prepend(board);
  check(angle(servo) === '180°', 'reconnecting controller adopts latest transport snapshot');
  servo.remove();
  replacement.publish(state(0x40, 2, 500));
  fixture.append(servo);
  check(angle(servo) === '0°', 'reconnecting servo adopts latest controller snapshot');
  board.transport = null;
  check(!servo.classList.contains('active'), 'clearing transport clears the servo signal');
  const host = document.createElement('section');
  fixture.append(host);
  const shadow = host.attachShadow({ mode: 'open' });
  shadow.innerHTML = '<gar-pca9685 id="board-a" address="0x40"></gar-pca9685><gar-sg90 id="shadow-servo" controller-id="board-a" channel="2"></gar-sg90>';
  shadow.getElementById('board-a').transport = replacement;
  check(angle(shadow.getElementById('shadow-servo')) === '0°', 'controller identities are scoped to their containing root');
  check(shadow.querySelectorAll('link[rel="stylesheet"]').length === 0,
    'component styles do not leak into the containing Product root');
  results.textContent = `${lines.join('\n')}\n${lines.length} passed`;
  document.documentElement.dataset.result = 'pass';
} catch (error) {
  results.textContent = `${lines.join('\n')}\nFAIL ${error.message}`;
  document.documentElement.dataset.result = 'fail';
  throw error;
}
