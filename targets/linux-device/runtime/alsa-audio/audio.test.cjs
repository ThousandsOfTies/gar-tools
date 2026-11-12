'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const {AlsaAudio, devices, checkWave} = require('./audio.cjs');

test('kernel inventory distinguishes USB capture/playback and named cards', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'alsa-cards-'));
  t.after(() => fs.rm(root, {recursive: true, force: true}));
  for (const [name, id, pcms, usb] of [['card2','Speakerphone',['pcm0p','pcm0c'],'1234:5678'], ['card0','HDMI',['pcm0p'],null]]) {
    await fs.mkdir(path.join(root, name));
    await fs.writeFile(path.join(root, name, 'id'), id + '\n');
    if (usb) await fs.writeFile(path.join(root, name, 'usbid'), usb + '\n');
    for (const pcm of pcms) await fs.mkdir(path.join(root, name, pcm));
  }
  const cards = await devices(root);
  assert.equal(cards.length, 2);
  assert.equal(cards[0].usb, null);
  assert.equal(cards[1].usb, '1234:5678');
  assert.deepEqual(cards[1].endpoints.map(p => p.direction).sort(), ['capture','playback']);
  assert.ok(cards[1].endpoints.every(p => p.device === 'plughw:CARD=Speakerphone,DEV=0'));
  assert.deepEqual(await devices(path.join(root, 'absent')), []);
});

test('capture/playback use explicit selectors, finite jobs and isolated devices', () => {
  const jobs = [], job = (command, args, options) => { jobs.push({command,args,options}); return {promise:Promise.resolve(),cancel(){}}; };
  const first = new AlsaAudio({job}), second = new AlsaAudio({job});
  first.record('/tmp/a.wav', 'plughw:CARD=Mic,DEV=0', 5);
  second.play('/tmp/b.wav', 'plughw:CARD=Speaker,DEV=1');
  assert.equal(jobs[0].command, 'arecord');
  assert.deepEqual(jobs[0].args.slice(-5), ['-c','1','-d','5','/tmp/a.wav']);
  assert.equal(jobs[0].options.timeoutMs, 10000);
  assert.deepEqual(jobs[1].args, ['-q','-D','plughw:CARD=Speaker,DEV=1','/tmp/b.wav']);
  assert.equal(jobs[1].options.timeoutMs, 30000);
  for (const value of [0,16,1.5,NaN]) assert.throws(() => first.record('a','default',value), /1..15/);
  for (const value of ['',null,'$(anything)','default\nfoo']) assert.throws(() => first.play('a',value), /explicit/);
  assert.equal(jobs.length, 2);
});

test('invalid and empty WAV data cannot pass replay validation', async t => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'alsa-wave-'));
  t.after(() => fs.rm(root, {recursive:true,force:true}));
  const file = path.join(root,'test.wav');
  await fs.writeFile(file, 'not a wav'); await assert.rejects(checkWave(file), /WAV/);
  const wave = Buffer.alloc(46); wave.write('RIFF'); wave.write('WAVE',8);
  await fs.writeFile(file,wave); await checkWave(file);
  await assert.rejects(checkWave(file,45), /bounded/);
});
