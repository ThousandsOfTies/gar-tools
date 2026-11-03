'use strict';
const fs=require('node:fs');
const path=require('node:path');

function validateProfile(profile,{allowLoopback=false}={}){
  if(!profile||typeof profile!=='object'||Array.isArray(profile))throw new Error('Invalid Live broker profile');
  let url;try{url=new URL(profile.url);}catch{throw new Error('Invalid Live broker URL');}
  if((url.protocol!=='https:'&&!(allowLoopback&&url.protocol==='http:'&&['127.0.0.1','localhost'].includes(url.hostname)))||
    url.username||url.password||url.search||url.hash||url.pathname!=='/api/live/token')throw new Error('Use an HTTPS Live token endpoint');
  if(!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(profile.deviceId||'')||!/^[A-Za-z0-9_-]{43}$/.test(profile.secret||''))throw new Error('Invalid device credential');
  return {url:url.href,deviceId:profile.deviceId,secret:profile.secret};
}

function loadProfile(file){
  if(!path.isAbsolute(file))throw new Error('Live broker profile must be an absolute path');
  try{
    const stat=fs.lstatSync(file);
    if(!stat.isFile()||stat.size>4096)throw new Error();
    if(process.platform!=='win32'&&(stat.mode&0o077))throw new Error();
    return validateProfile(JSON.parse(fs.readFileSync(file,'utf8')));
  }catch{throw new Error('Cannot read a private Live broker profile (use a regular file, mode 0600)');}
}

async function readLimited(response){
  const reader=response.body?.getReader();if(!reader)throw new Error('Empty broker response');
  const chunks=[];let length=0;
  try{while(true){const {done,value}=await reader.read();if(done)break;length+=value.length;
    if(length>16384)throw new Error('Oversized broker response');chunks.push(value);}
  }catch(error){await reader.cancel().catch(()=>{});throw error;}
  return Buffer.concat(chunks).toString('utf8');
}

/** Provider credentials stay in memory. No App, GPIO, microphone or logging. */
async function requestToken(profile,{fetchImpl=globalThis.fetch,signal,now=Date.now,allowLoopback=false}={}){
  const selected=validateProfile(profile,{allowLoopback});
  let response;
  try{response=await fetchImpl(selected.url,{method:'POST',redirect:'error',cache:'no-store',
    headers:{Authorization:`Bearer ${selected.deviceId}.${selected.secret}`,'Content-Type':'application/json'},body:'{}',
    signal:signal?AbortSignal.any([signal,AbortSignal.timeout(15000)]):AbortSignal.timeout(15000)});
  }catch{throw new Error(signal?.aborted?'Live token request cancelled':'Cannot reach the Live token broker');}
  if(!response.ok){await response.body?.cancel().catch(()=>{});throw new Error(`Live token broker HTTP ${response.status}`);}
  try{
    const value=JSON.parse(await readLimited(response)),time=now(),expires=Date.parse(value.expiresAt),newSession=Date.parse(value.newSessionExpiresAt);
    if(typeof value.token!=='string'||!value.token.startsWith('auth_tokens/')||value.token.length>8192||
      !/^gemini-[\w.-]{1,90}$/.test(value.model||'')||!['v1alpha','v1beta'].includes(value.apiVersion)||
      !Number.isFinite(expires)||expires<=time||expires>time+31*60_000||
      !Number.isFinite(newSession)||newSession<=time||newSession>time+65_000||newSession>expires)throw new Error();
    return {ephemeralToken:value.token,model:value.model,apiVersion:value.apiVersion,expiresAt:value.expiresAt};
  }catch{throw new Error('Invalid or expired Live token response; check the device clock');}
}

module.exports={loadProfile,validateProfile,requestToken};
