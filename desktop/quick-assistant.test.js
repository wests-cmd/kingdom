const {test} = require('node:test');
const assert = require('node:assert/strict');
const {EventEmitter} = require('node:events');
const {QuickAssistant,ACCELERATOR} = require('./quick-assistant');

function fixture(overrides={}) {
  const calls = {created:0,registered:0,unregistered:0};
  class Window extends EventEmitter {
    constructor(options) {
      super();calls.created++;this.options=options;this.webContents=new EventEmitter();
      this.webContents.setWindowOpenHandler=handler=>this.openHandler=handler;
    }
    isDestroyed(){return !!this.destroyed}
    isMinimized(){return false}
    async loadURL(url){this.url=url}
    show(){this.visible=true}
    focus(){this.focused=true}
    destroy(){this.destroyed=true;this.emit('closed')}
  }
  const assistant=new QuickAssistant({BrowserWindow:Window,
    globalShortcut:{register(key,handler){assert.equal(key,ACCELERATOR);calls.registered++;calls.handler=handler;return true},
      unregister(key){assert.equal(key,ACCELERATOR);calls.unregistered++}},
    allowed:()=>true,ready:async()=>true,origin:()=> 'http://127.0.0.1:8000',...overrides});
  return {assistant,calls};
}
test('one compact native window, sandboxed, no privileged preload or external navigation',async()=>{
  const {assistant,calls}=fixture();
  assert.equal(assistant.register(),true);
  assert.equal(assistant.register(),true);
  assert.equal(calls.registered,1);
  assert.equal(await assistant.open(),true);
  const w=assistant.window;
  assert.equal(w.url,'http://127.0.0.1:8000/#/quick');
  assert.deepEqual(w.options.webPreferences,{sandbox:true,nodeIntegration:false,contextIsolation:true});
  assert.deepEqual(w.openHandler(),{action:'deny'});
  let blocked=0;
  for(const event of ['will-navigate','will-redirect']) {
    w.webContents.emit(event,{preventDefault(){blocked++}},'https://example.com');
  }
  assert.equal(blocked,2);
  assert.equal(await assistant.open(),true);
  assert.equal(calls.created,1);
  w.destroy();
  assert.equal(await assistant.open(),true);
  assert.equal(calls.created,2);
  assistant.stop();assistant.stop();
  assert.equal(calls.unregistered,1);
  assert.equal(assistant.window,null);
  assert.equal(await assistant.open(),false);
});
test('headless and unavailable backends cannot open the assistant',async()=>{
  const headless=fixture({allowed:()=>false});
  assert.equal(headless.assistant.register(),false);
  assert.equal(await headless.assistant.open(),false);
  assert.equal(headless.calls.created,0);
  const unready=fixture({ready:async()=>false});
  assert.equal(await unready.assistant.open(),false);
  assert.equal(unready.calls.created,0);
});
test('shortcut collision leaves explicit tray opening available',async()=>{
  const {assistant}=fixture({globalShortcut:{register:()=>false,unregister:()=>assert.fail('not owned')}});
  assert.equal(assistant.register(),false);
  assert.equal(await assistant.open(),true);
  assistant.stop();
});
test('parallel opens and quit during readiness cannot create extra windows',async()=>{
  let release;
  const {assistant,calls}=fixture({ready:()=>new Promise(resolve=>release=resolve)});
  const pending=assistant.open();
  assert.equal(await assistant.open(),false);
  assistant.stop();release(true);
  assert.equal(await pending,false);
  assert.equal(calls.created,0);
});

test('eligibility lost during renderer load destroys hidden window',async()=>{
  let allowed=true;
  const {assistant}=fixture({allowed:()=>allowed});
  const original=assistant.BrowserWindow.prototype.loadURL;
  assistant.BrowserWindow.prototype.loadURL=async function(url){
    await original.call(this,url);
    allowed=false;
  };
  assert.equal(await assistant.open(),false);
  assert.equal(assistant.window,null);
});
test('failed renderer load destroys window and allows retry',async()=>{
  const {assistant,calls}=fixture();
  const original=assistant.BrowserWindow.prototype.loadURL;
  assistant.BrowserWindow.prototype.loadURL=async()=>{throw new Error('load failed')};
  await assert.rejects(assistant.open(),/load failed/);
  assert.equal(assistant.window,null);
  assistant.BrowserWindow.prototype.loadURL=original;
  assert.equal(await assistant.open(),true);
  assert.equal(calls.created,2);
  assistant.stop();
});
