const {test} = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const MobileClient = require('./index');

test('mobile scaffold no longer returns invented ready or pairing codes',async()=>{
 const client = new MobileClient();
 await assert.rejects(client.fetchPairingChallenge(),/owner creates/);
 assert.throws(()=>new MobileClient('http://example.com',{sessionToken:'controlled-test-session'}),/HTTPS/);
});

test('mobile status uses actual version and bounded session responses',async()=>{
 const server = http.createServer((request,response)=>{
  response.setHeader('Content-Type','application/json');
  if(request.url==='/api/system/version') response.end(JSON.stringify({version:'test-version'}));
  else if(request.url==='/mobile/session/status' && request.headers.authorization==='Bearer controlled-test-session') response.end(JSON.stringify({success:true,device_state:'APPROVED'}));
  else {response.statusCode=401;response.end('{}');}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try {
  const origin=`http://127.0.0.1:${server.address().port}`;
  assert.deepEqual(await new MobileClient(origin).getCommanderStatus(),{version:'test-version',device_state:'not_connected',session_verified:false});
  assert.deepEqual(await new MobileClient(origin,{sessionToken:'controlled-test-session'}).getCommanderStatus(),{version:'test-version',device_state:'APPROVED',session_verified:true});
  await assert.rejects(new MobileClient(origin,{sessionToken:'revoked'}).getCommanderStatus(),/revoked/);
 } finally {await new Promise(resolve=>server.close(resolve));}
});
