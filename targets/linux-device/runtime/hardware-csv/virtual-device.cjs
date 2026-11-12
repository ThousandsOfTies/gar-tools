'use strict';
const fs=require('node:fs');

/** Same CSV device path; refuse a physical controller before any simulated motion. */
function requireVirtualI2c(device,io=fs){
  if(!/^\/dev\/i2c-\d+$/.test(device))throw new Error('Invalid I2C device path');
  const information=io.statSync(device,{bigint:true});
  if(!information.isCharacterDevice())throw new Error('I2C device is not a character device');
  const number=BigInt(information.rdev);
  const major=((number>>8n)&0xfffn)|((number>>32n)&~0xfffn);
  const minor=(number&0xffn)|((number>>12n)&~0xffn);
  const actual=io.realpathSync(`/sys/dev/char/${major}:${minor}`);
  if(!actual.includes('/virtual/cuse/'))throw new Error('Simulation requires a CUSE virtual I2C device');
  return device;
}
module.exports={requireVirtualI2c};
