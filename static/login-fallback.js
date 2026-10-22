// If the sign-in bundle never loads (blocked script, CDN or network failure), replace the
// indefinite "Loading" message with an actionable one instead of leaving a dead page.
setTimeout(()=>{
 const slot=document.getElementById('privy-login');
 if(!slot||!document.getElementById('signin-loading'))return;
 slot.innerHTML='<p class="auth-error" role="alert">Secure sign-in could not load. Check your connection or content blocker, then <a href="">reload this page</a>.</p>';
},12000);
