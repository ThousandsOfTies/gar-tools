'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {requestToken,loadProfile,validateProfile}=require('./broker.cjs');
const time=1_800_000_000_000;
const profile={url:'https://example.test/api/live/token',deviceId:'first-device',secret:'a'.repeat(43)};
const token=()=>({token:'auth_tokens/test-only-token',model:'gemini-3.8-live',apiVersion:'v1alpha',
  expiresAt:new Date(time+30*60_000).toISOString(),newSessionExpiresAt:new Date(time+60_000).toISOString()});

test('two independent device clients fetch constrained credentials without importing an App',async()=>{
  const requests=[];
  const fetchImpl=async(url,options)=>{requests.push({url,options});return Response.json(token());};
  for(const selected of [profile,{...profile,deviceId:'second-device',secret:'b'.repeat(43)}]){
    const result=await requestToken(selected,{fetchImpl,now:()=>time});
    assert.equal(result.ephemeralToken,'auth_tokens/test-only-token');assert.equal(result.apiVersion,'v1alpha');
    assert.ok(!JSON.stringify(result).includes(selected.secret));
  }
  assert.notEqual(requests[0].options.headers.Authorization,requests[1].options.headers.Authorization);
  assert.equal(requests[0].options.redirect,'error');assert.equal(requests[0].options.body,'{}');
  assert.ok(!requests[0].url.includes(profile.secret));
});

test('profiles reject redirects, accidental cleartext transport and credential-bearing URLs',()=>{
  for(const url of ['http://example.test/api/live/token','https://user:pass@example.test/api/live/token',
    'https://example.test/api/live/token?key=secret','https://example.test/other'])assert.throws(()=>validateProfile({...profile,url}));
  assert.throws(()=>validateProfile({...profile,deviceId:'../invalid'}));
  assert.throws(()=>validateProfile({...profile,secret:'short'}));
});

test('network and provider errors never expose request headers or response secrets',async()=>{
  for(const fetchImpl of [async()=>{throw new Error(profile.secret);},async()=>new Response(profile.secret,{status:401}),
    async()=>Response.json({error:profile.secret}),async()=>Response.json({...token(),token:profile.secret})]){
    await assert.rejects(requestToken(profile,{fetchImpl,now:()=>time}),error=>!error.message.includes(profile.secret));
  }
});

test('expired or long-lived tokens, invalid models and oversized responses are rejected',async()=>{
  for(const value of [{...token(),newSessionExpiresAt:new Date(time-1).toISOString()},
    {...token(),expiresAt:new Date(time+40*60_000).toISOString()},
    {...token(),model:'https://example.test'}, {...token(),apiVersion:'v9'},
    {...token(),extra:'x'.repeat(20000)}]){
    await assert.rejects(requestToken(profile,{fetchImpl:async()=>Response.json(value),now:()=>time}));
  }
});

test('a cancelled request cannot leak the credential in an error',async()=>{
  const cancel=new AbortController();cancel.abort();
  await assert.rejects(requestToken(profile,{signal:cancel.signal,fetchImpl:async()=>{throw new Error(profile.secret);}}),/cancelled/);
});

test('credential profiles are regular, private files and never appear in parser errors',()=>{
  const directory=fs.mkdtempSync(path.join(os.tmpdir(),'gar-live-broker-')),file=path.join(directory,'device.json');
  try{
    fs.writeFileSync(file,JSON.stringify(profile),{mode:0o600});
    assert.deepEqual(loadProfile(file),profile);
    fs.writeFileSync(file,profile.secret);
    assert.throws(()=>loadProfile(file),error=>!error.message.includes(profile.secret));
    fs.writeFileSync(file,JSON.stringify(profile));
    if(process.platform!=='win32'){fs.chmodSync(file,0o644);assert.throws(()=>loadProfile(file),/0600/);}
  }finally{fs.unlinkSync(file);fs.rmdirSync(directory);}
});
