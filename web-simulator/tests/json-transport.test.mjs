import assert from 'node:assert/strict';
import test from 'node:test';
import { JsonTransport } from '../components/json-transport.mjs';

class Socket extends EventTarget {
  static OPEN = 1;
  static instances = [];
  constructor(url) { super(); this.url = url; this.readyState = 0; this.sent = []; Socket.instances.push(this); }
  send(data) { this.sent.push(JSON.parse(data)); }
  close() { this.readyState = 3; this.dispatchEvent(new Event('close')); }
  open() { this.readyState = 1; this.dispatchEvent(new Event('open')); }
  receive(data) { this.dispatchEvent(new MessageEvent('message', { data })); }
}

test('JSON transport connects explicitly to independent endpoints and passes arbitrary messages', () => {
  const previous = globalThis.WebSocket;
  globalThis.WebSocket = Socket;
  Socket.instances.length = 0;
  const a = new JsonTransport({ url: 'ws://localhost/a' });
  const b = new JsonTransport({ url: 'ws://localhost/b' });
  try {
    assert.equal(Socket.instances.length, 0);
    assert.equal(a.send({ value: 1 }), false);
    a.connect(); b.connect();
    const [first, second] = Socket.instances;
    assert.deepEqual([first.url, second.url], ['ws://localhost/a', 'ws://localhost/b']);
    const events = [];
    a.addEventListener('message', ({detail}) => events.push(detail));
    first.open(); second.open();
    first.receive('{"reading":7}'); second.receive('{"reading":9}'); first.receive('invalid JSON');
    assert.deepEqual(events, [{ reading: 7 }]);
    assert.equal(a.send({ command: 'sample' }), true);
    assert.deepEqual(first.sent, [{ command: 'sample' }]);
    a.close(); first.receive('{"reading":99}');
    assert.equal(a.connected, false); assert.equal(b.connected, true);
    assert.deepEqual(events, [{ reading: 7 }]);
  } finally { a.close(); b.close(); globalThis.WebSocket = previous; }
});

test('closing from a disconnect listener prevents stale reconnection', async () => {
  const previous = globalThis.WebSocket;
  globalThis.WebSocket = Socket;
  Socket.instances.length = 0;
  const transport = new JsonTransport({ url: 'ws://localhost/test', reconnectMs: 1 });
  try {
    transport.connect(); Socket.instances[0].open();
    transport.addEventListener('connection', ({detail}) => { if (!detail.connected) transport.close(); });
    Socket.instances[0].close();
    await new Promise(resolve => setTimeout(resolve, 15));
    assert.equal(Socket.instances.length, 1);
  } finally { transport.close(); globalThis.WebSocket = previous; }
});
