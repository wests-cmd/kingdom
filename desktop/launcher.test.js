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
