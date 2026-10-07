import { Browser } from '@capacitor/browser';
import { connectionUrl } from './connection.js';
import './style.css';
const form=document.querySelector('form'), address=document.querySelector('#address'), status=document.querySelector('#status');
address.value=localStorage.getItem('kingdom-origin') || '';
form.addEventListener('submit',async event=>{
 event.preventDefault(); status.textContent='';
 try {const url=connectionUrl(address.value);await Browser.open({url});localStorage.setItem('kingdom-origin',new URL(url).origin);status.textContent='Enter your pairing code in Kingdom’s connection page. Return here to open another server.';}
 catch(error){status.textContent=error.message || 'Could not open Kingdom. Check the address and network connection.';}
});
