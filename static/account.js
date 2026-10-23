'use strict';

function accountPage(){
 return heading('Account','Your profile and workspaces.')+
  '<div id="accountContent" role="status">Loading account…</div>';
}

async function mountAccount(){
 const node=document.getElementById('accountContent');
 if(!node)return;
 try{
  const [profile,organization]=await Promise.all([
   json('/account'),json('/organizations/current')]);
  if(!node.isConnected)return;
  const individual=['privy','dynamic'].includes(profile.authentication_kind);
  const provider=profile.authentication_kind==='privy'?'Privy':profile.authentication_kind==='dynamic'?'Dynamic':'Development / team token';
  const initials=(profile.display_name||'GT').trim().split(/\s+/).slice(0,2).map(word=>word[0]||'').join('').toUpperCase();
  document.getElementById('accountAvatar').textContent=initials||'GT';
  const joined=profile.created?new Date(profile.created*1000).toLocaleDateString():null;
  const workspaces=profile.organizations||[];
  node.removeAttribute('role');
  node.innerHTML=`<div class="account-hero panel"><span class="account-initials" aria-hidden="true">${escapeHtml(initials)}</span><div><span class="eyebrow">YOUR ACCOUNT</span><h2>${escapeHtml(profile.display_name)}</h2><p>${escapeHtml(provider)} sign-in${joined?' · Member since '+escapeHtml(joined):''}</p></div></div>
   <div class="account-grid"><section class="panel account-card"><div class="panel-header"><h2>Profile</h2><span class="chip">${individual?'Personal':'Read only'}</span></div><div class="form-body"><div class="field"><span class="field-label">Email</span><span id="accountEmail" class="account-email" aria-live="polite">${profile.authentication_kind==='privy'?'Loading your sign-in email…':'No email available for this sign-in method.'}</span></div>${individual?`<form id="accountForm"><div class="field"><label for="accountDisplayName">Display name</label><input id="accountDisplayName" name="display_name" autocomplete="name" required minlength="2" maxlength="80" value="${escapeHtml(profile.display_name)}"><small>Shown to members of your workspaces.</small></div><p id="accountError" class="inline-error" role="alert" hidden></p><button class="button primary" type="submit">Save profile</button></form>`:'<p>Sign in with an individual account to edit your profile.</p>'}</div></section>
   <section class="panel account-card"><div class="panel-header"><h2>Workspaces</h2><span class="chip">${workspaces.length||1} available</span></div><div class="form-body"><p class="account-current">${escapeHtml(organization.name)} <span class="chip">${escapeHtml(profile.role)}</span></p>${workspaces.length>1?`<ul class="account-workspaces">${workspaces.map(item=>`<li>${escapeHtml(item.name)}${item.id===profile.active_organization_id?' · active':''}</li>`).join('')}</ul>`:''}<a class="button primary" href="#/team">Manage team & workspaces →</a></div></section>
   <section class="panel account-card"><div class="panel-header"><h2>Sign-in & session</h2></div><div class="form-body"><p>Signed in with ${escapeHtml(provider)}.</p><div class="account-actions"><button class="button" id="accountSignOut" type="button">Sign out</button></div></div></section></div>
   <section class="panel account-card account-tools"><div class="panel-header"><h2>Workspace tools</h2></div><div class="form-body account-actions"><a class="button primary" href="#/team">Team & workspaces</a><a class="button" href="#/physical">Physical recordings</a><a class="button" href="#/benchmarks">Benchmark coverage</a><a class="button" href="#/scenarios">Scenario library</a><a class="button" href="#/reports">Evidence reports</a><a class="button" href="#/new">Manual trial</a></div></section>`;
  if(profile.authentication_kind==='privy'){
   const emailNode=node.querySelector('#accountEmail');
   import('/assets/auth/account-email.js').then(module=>{
    if(emailNode.isConnected)module.mountAccountEmail(emailNode,profile.subject);
   }).catch(()=>{if(emailNode.isConnected)emailNode.textContent='Sign-in email unavailable.';});
  }
  const form=node.querySelector('#accountForm');
  if(form)form.onsubmit=async event=>{
   event.preventDefault();
   const button=form.querySelector('[type="submit"]'),error=form.querySelector('#accountError');
   button.disabled=true;error.hidden=true;
   try{
    await json('/account',{method:'PATCH',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({display_name:form.elements.display_name.value.trim()})});
    notify('Profile updated.');
    await mountAccount();
   }catch(err){error.textContent=err.message;error.hidden=false;button.disabled=false;}
  };
  node.querySelector('#accountSignOut').onclick=signOut;
 }catch(error){if(node.isConnected){node.removeAttribute('role');node.textContent=error.message;}}
}
