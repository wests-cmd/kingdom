const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const {candidate, newer, verifyFile, handoffScript, DesktopUpdates} = require('./updates');
const release = () => ({tag_name:'v1.2.1', assets:[{name:'Kingdom-Setup-1.2.1.exe',size:3,digest:'sha256:'+'a'.repeat(64),browser_download_url:'https://github.com/wests-cmd/kingdom/releases/download/v1.2.1/Kingdom-Setup-1.2.1.exe'}]});
test('only newer stable releases with fixed URLs, bounded sizes and digests are accepted',()=>{
 assert.equal(candidate(release(),'1.2.0').available,true);
 assert.equal(candidate(release(),'1.2.1').available,false);
 assert.equal(newer('1.10.0','1.9.9'),true);
 for(const change of [r=>r.prerelease=true,r=>r.assets[0].digest=null,r=>r.assets[0].browser_download_url='https://example.com/setup.exe',r=>r.assets[0].size=600*1024*1024]){
  const r=release();change(r);assert.throws(()=>candidate(r,'1.2.0'));
 }
 assert.throws(()=>newer('1.2.1;command','1.2.0'));
});
test('staged installers are rechecked and tampering is rejected',async()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'kingdom-update-test-'));
 try{
  const file=path.join(directory,'setup.exe');fs.writeFileSync(file,'abc');
  const expected={size:3,sha256:crypto.createHash('sha256').update('abc').digest('hex')};
  await verifyFile(file,expected);fs.writeFileSync(file,'bad');await assert.rejects(()=>verifyFile(file,expected));
 }finally{fs.rmSync(directory,{recursive:true,force:true,maxRetries:20,retryDelay:100})}
});
test('cached downloads survive restarts but cannot select an outside installer',()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'kingdom-update-cache-'));
 try{
  fs.mkdirSync(path.join(directory,'updates'));
  const r=release(),saved=candidate(r,'1.2.0');
  fs.writeFileSync(path.join(directory,'updates',saved.name),'abc');
  fs.writeFileSync(path.join(directory,'updates','ready.json'),JSON.stringify(saved));
  const app={getPath:()=>directory,getVersion:()=> '1.2.0',isPackaged:true};
  assert.equal(new DesktopUpdates(app).ready.update.latest,'1.2.1');
  saved.name='../outside.exe';fs.writeFileSync(path.join(directory,'updates','ready.json'),JSON.stringify(saved));
  assert.equal(new DesktopUpdates(app).ready,null);
 }finally{fs.rmSync(directory,{recursive:true,force:true})}
});
test('handoff waits for shutdown, rechecks bytes, preserves data and verifies installation',()=>{
 const script=handoffScript(42,"C:\\Owner's Folder\\setup.exe","C:\\Kingdom\\Kingdom.exe",'a'.repeat(64),'1.2.1','C:\\updates\\result.json');
 assert.match(script,/Wait-Process -Id 42/);assert.match(script,/Owner''s Folder/);
 assert.match(script,/Get-FileHash/);assert.match(script,/ProductVersion/);assert.match(script,/finally/);
 assert.doesNotMatch(script,/Uninstall|Remove-Item.*-Recurse/);
 assert.throws(()=>handoffScript('42;bad','x','y','z','1.2.1','r'));
});

test('Windows helper survives its launcher and rejects a missing installer', {skip:process.platform!=='win32'}, async()=>{
 const {spawn}=require('child_process');
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'kingdom-handoff-'));
 const receipt=path.join(directory,'result.json');
 try{
  const moduleFile=path.resolve(__dirname,'updates.js');
  const source="const {handoffScript,launchHandoff}=require(process.argv[1]);const path=require('path');const r=process.argv[2];launchHandoff(handoffScript(process.pid,path.join(path.dirname(r),'missing.exe'),path.join(path.dirname(r),'missing-app.exe'),'a'.repeat(64),'1.2.1',r),r).catch(()=>process.exit(1));";
  await new Promise((resolve,reject)=>{
   const child=spawn(process.execPath,['-e',source,moduleFile,receipt],{stdio:'ignore'});
   const timeout=setTimeout(()=>{child.kill();reject(new Error('Launcher did not release helper'))},10000);
   child.once('error',reject);child.once('exit',code=>{clearTimeout(timeout);code===0?resolve():reject(new Error('Launcher failed'))});
  });
  for(let attempt=0;attempt<50&&!fs.existsSync(receipt);attempt++)await new Promise(resolve=>setTimeout(resolve,100));
  const result=JSON.parse(fs.readFileSync(receipt,'utf8').replace(/^\uFEFF/,''));
  assert.equal(result.success,false);
  assert.equal(result.reopenedPID,undefined);
 }finally{fs.rmSync(directory,{recursive:true,force:true})}
});
