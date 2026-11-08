import assert from 'node:assert/strict';
import test from 'node:test';
import { emptyPca9685State, pca9685StateFromMessage, channelPulse, pulseToPreviewAngle } from '../components/servo-model.mjs';
import { GamepadReader } from '../components/gamepad-model.mjs';
import { TelemetryTransport } from '../components/telemetry-transport.mjs';

test('two PCA9685 boards can consume the same snapshot and independent updates', () => {
  const first = { ...emptyPca9685State(), address: 0x40, device: '/dev/i2c-1', frequencyHz: 50 };
  const second = { ...emptyPca9685State(), address: 0x41, device: '/dev/i2c-1', frequencyHz: 60 };
  const message = { type: 'init', state: { i2c: { pca9685: [first, second] } } };
  assert.equal(pca9685StateFromMessage(message, undefined, { address: 0x40 }).frequencyHz, 50);
  const observed = pca9685StateFromMessage(message, undefined, { address: 0x41 });
  assert.equal(observed.frequencyHz, 60);
  assert.equal(pca9685StateFromMessage({ type: 'pca9685', ...first }, observed, { address: 0x41 }), observed);
  assert.equal(pca9685StateFromMessage({ type: 'init', state: null }, observed).frequencyHz, null);
  assert.equal(pca9685StateFromMessage(message, undefined, { device: '/dev/i2c-2' }).frequencyHz, null);
});

test('servo preview uses per-instance calibration and wrapped PWM counters', () => {
  const pulse = channelPulse({ on: 4000, off: 211, fullOn: false, fullOff: false }, 50);
  assert.equal(pulse.counts, 307);
  assert.ok(Math.abs(pulseToPreviewAngle(pulse.pulseUs, 1000, 2000) - 90) < 1);
  assert.equal(pulseToPreviewAngle(500, 1000, 2000), 0);
  assert.equal(pulseToPreviewAngle(2500, 1000, 2000), 180);
});

test('telemetry accepts any application state, remains read-only and detaches stale sockets', () => {
  const previousWebSocket = globalThis.WebSocket;
  const sockets = [];
  globalThis.WebSocket = class {
    constructor(url) { this.url = url; sockets.push(this); }
    close() { this.closed = true; }
    send() { assert.fail('A telemetry subscription must never send device commands'); }
  };
  const transport = new TelemetryTransport({
    url: 'ws://localhost:9999/telemetry',
    initialState: () => ({ temperature: 21 }),
    reduceMessage: (message, state) => message.type === 'temperature' ? { temperature: message.value } : state,
  });
  try {
    transport.publish({ temperature: 25 });
    assert.equal(transport.state.temperature, 25);
    transport.select('live');
    const socket = sockets[0];
    assert.equal(socket.url, 'ws://localhost:9999/telemetry');
    socket.onmessage({ data: JSON.stringify({ type: 'temperature', value: 32 }) });
    transport.publish({ temperature: 99 });
    assert.equal(transport.state.temperature, 32);
    socket.onmessage({ data: 'null' });
    assert.equal(transport.state.temperature, 32);
    const staleClose = socket.onclose;
    transport.select('demo');
    staleClose();
    assert.equal(transport.state.temperature, 21);
    assert.equal(transport.retry, null);
    assert.equal(socket.closed, true);
    assert.equal(socket.onmessage, null);
  } finally {
    transport.close();
    globalThis.WebSocket = previousWebSocket;
  }
});

test('gamepad input is motion-independent and starts only from neutral', () => {
  const reader = new GamepadReader();
  const pad = axes => ({ connected: true, mapping: 'standard', axes, buttons: [] });
  assert.deepEqual(reader.sample(pad([1, 0])), []);
  assert.deepEqual(reader.sample(pad([0, 0])), []);
  assert.deepEqual(reader.sample(pad([1, 0])), [{ type: 'axes', axes: [1, 0] }]);
  assert.deepEqual(reader.sample(null), [{ type: 'stop' }]);
});

test('B and simultaneous buttons preserve axes until a consumer explicitly cancels', () => {
  const reader = new GamepadReader();
  const pad = (axes, pressed = []) => ({ connected: true, mapping: 'standard', axes,
    buttons: Array.from({ length: 16 }, (_, i) => ({ pressed: pressed.includes(i) })) });
  reader.sample(pad([0, 0]));
  assert.deepEqual(reader.sample(pad([1, 0], [0, 1, 2])), [
    { type: 'axes', axes: [1, 0] }, { type: 'button', button: 'a' },
    { type: 'button', button: 'b' }, { type: 'button', button: 'x' },
  ]);
  assert.equal(reader.ready, true);
  assert.deepEqual(reader.sample(pad([1, 0], [0, 1, 2])), []);
  assert.ok(reader.sample(pad([.5, 0])).some(event => event.type === 'axes'));
  reader.reset();
  assert.deepEqual(reader.sample(pad([1, 0])), []);
  reader.sample(pad([0, 0]));
  assert.equal(reader.ready, true);
});

test('a disconnect listener can leave live mode without scheduling a stale reconnect', () => {
  const previousWebSocket = globalThis.WebSocket;
  let socket;
  globalThis.WebSocket = class {
    constructor() { socket = this; }
    close() {}
  };
  const transport = new TelemetryTransport({ url: 'ws://localhost/telemetry', initialState: () => ({ value: 1 }) });
  try {
    transport.select('live');
    const messages = [];
    transport.addEventListener('message', ({ detail }) => messages.push(detail));
    transport.addEventListener('connection', ({ detail }) => {
      if (detail.mode === 'live' && !detail.connected) transport.select('demo');
    });
    socket.onclose();
    assert.equal(transport.mode, 'demo');
    assert.equal(transport.retry, null);
    assert.deepEqual(messages.at(-1).state, { value: 1 });
  } finally {
    transport.close();
    globalThis.WebSocket = previousWebSocket;
  }
});
