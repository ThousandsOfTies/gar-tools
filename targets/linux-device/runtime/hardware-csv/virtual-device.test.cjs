'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {requireVirtualI2c}=require('./virtual-device.cjs');
test('canonical bus numbers work only when backed by CUSE',()=>{
  for(const number of [1,3,10,99]){
    const io={statSync:()=>({rdev:BigInt(240*256+number),isCharacterDevice:()=>true}),
      realpathSync:()=>`/sys/devices/virtual/cuse/i2c-${number}`};
    assert.equal(`/dev/i2c-${number}`,requireVirtualI2c(`/dev/i2c-${number}`,io));
    io.realpathSync=()=>'/sys/devices/platform/physical-i2c/i2c-1';
    assert.throws(()=>requireVirtualI2c(`/dev/i2c-${number}`,io),/CUSE/);
  }
});
test('ordinary files and malformed paths cannot pass the motion gate',()=>{
  assert.throws(()=>requireVirtualI2c('/dev/i2c-1',{statSync:()=>({isCharacterDevice:()=>false})}),/character/);
  assert.throws(()=>requireVirtualI2c('/dev/i2c-1/../../physical'),/Invalid/);
});
