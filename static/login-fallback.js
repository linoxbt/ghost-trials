// If the sign-in bundle never loads (blocked script, CDN or network failure), replace the
// indefinite "Loading" message with an actionable one instead of leaving a dead page.
setTimeout(()=>{
 const slot=document.getElementById('privy-login');
 if(!slot||!document.getElementById('signin-loading'))return;
 slot.innerHTML='<p class="auth-error" role="alert">Secure sign-in could not load. Check your connection or content blocker, then <a href="">reload this page</a>.</p>';
},12000);

// A rejected deployment token returns here with a reason; show it next to the form.
const tokenError=new URLSearchParams(location.search).get('token_error');
if(tokenError){
 const line=document.getElementById('token-error');
 line.textContent=tokenError==='rate'?'Too many failed attempts. Wait a minute, then try again.':'That access token was not accepted. Check it and try again.';
 line.hidden=false;
 const team=document.getElementById('private-team');team.hidden=false;team.open=true;
}

// The token form returns to the same workspace route as the provider sign-in (the server validates it).
const tokenNext=document.getElementById('token-next');
if(tokenNext)tokenNext.value=new URLSearchParams(location.search).get('next')||(location.hash.startsWith('#/')?location.hash:'');
