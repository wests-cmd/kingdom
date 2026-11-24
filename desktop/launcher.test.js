const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const {EventEmitter}=require('node:events');

for(const bundled of [false,true])test(`Windows ${bundled?'bundled':'development'} backend starts without a console`,()=>{
 const calls=[];const child=new EventEmitter();child.pid=123;
 const module={exports:{}};
 const realRequire=require;
 const context={module,__dirname:__dirname,console:{log(){},error(){}},setTimeout,
  process:{platform:'win32',env:{KINGDOM_BACKEND_BIN:'C:/fixture/backend.exe'}},
  require(name){
   if(name==='child_process')return {spawn(...args){calls.push(args);return child},spawnSync(){}};
   if(name==='fs')return {existsSync:()=>bundled,mkdirSync(){}};
   return realRequire(name);
  }};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'launcher.js'),'utf8'),context);
 context.module.exports.startBackend('C:/fixture/profile.json');
 assert.equal(calls.length,1);
 assert.equal(calls[0][2].windowsHide,true);
 assert.equal(calls[0][2].detached,false);
});


test('Readiness polls promptly, accepts only HTTP 200, and does not require external tools', async()=>{
 const tries=[];const delays=[];const module={exports:{}};let response=0;
 const context={module,__dirname:__dirname,console:{log(){},error(){}},
  process:{platform:'linux',env:{PORT:'8000'}},
  setTimeout(callback,delay){delays.push(delay);queueMicrotask(callback);},
  require(name){
   if(name==='http')return {get(url,respond){
    tries.push(url);const request=new EventEmitter();
    request.setTimeout=()=>request;
    response++;
    const count=response;
    queueMicrotask(()=>{
     if(count===1)respond({statusCode:503,resume(){}});
     else if(count===2)request.emit('error',new Error('not ready'));
     else respond({statusCode:200,resume(){}});
    });
    return request;
   }};
   return require(name);
  }};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'launcher.js'),'utf8'),context);
 assert.equal(await context.module.exports.waitForBackendReady(),true);
 assert.equal(tries.length,3);
 assert.equal(tries[0],'http://127.0.0.1:8000/health/ready');
 assert.deepEqual(delays,[250,250]);
});
