import test from 'node:test';import assert from 'node:assert/strict';import {connectionUrl} from '../src/connection.js';
test('uses the supplied HTTPS server and connection route',()=>assert.equal(connectionUrl(' https://laptop.tailnet.ts.net '),'https://laptop.tailnet.ts.net/#/connect'));
test('rejects cleartext, credentials and hidden routes or queries',()=>{for(const url of ['http://host','https://user:password@host','https://host/path','https://host/?token=x','https://host/#route','file:///etc/passwd','javascript:alert(1)'])assert.throws(()=>connectionUrl(url));});
