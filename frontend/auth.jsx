import React, {useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {PrivyProvider,useLinkAccount,useLoginWithPasskey,usePrivy,useSignupWithPasskey} from '@privy-io/react-auth';

async function api(path,body){
  const response=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',
    headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
  let data;
  try{data=await response.json();}catch{data={};}
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:
    response.status===502?'The Ghost Trials backend is unavailable. Please try again after service is restored.':'Unable to complete sign-in. Please try again.');
  return data;
}
function SignIn({methods,passkeySignupEnabled}){
  const {ready,authenticated,login,getAccessToken,logout}=usePrivy();
  const [error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [passkeyNotice,setPasskeyNotice]=useState('');
  const {loginWithPasskey,state:passkeyLogin}=useLoginWithPasskey({onError:(err)=>setError(err.message)});
  const {signupWithPasskey,state:passkeySignup}=useSignupWithPasskey({onError:(err)=>setError(err.message)});
  const {linkPasskey}=useLinkAccount({
    onSuccess:()=>setPasskeyNotice('Passkey created for this account. You can use it to sign in next time.'),
    onError:(err)=>setError(typeof err==='string'?err:err.message),
  });
  const passkeyEnabled=methods.includes('passkey');
  const passkeyBusy=['generating-challenge','awaiting-passkey','submitting-response'].includes(passkeyLogin.status)||
    ['generating-challenge','awaiting-passkey','submitting-response'].includes(passkeySignup.status);
  async function beginPasskey(action){
    setError('');setPasskeyNotice('');
    try{await action();}
    catch(err){setError(err instanceof Error?err.message:'Passkey request failed. Please try again.');}
  }
  async function enter(){
    setBusy(true);setError('');
    try{
      const access_token=await getAccessToken();
      if(!access_token)throw new Error('Please sign in again.');
      await api('/auth/privy/session',{access_token});
      const invite=location.pathname==='/auth/invite'?location.hash.slice(1):'';
      if(invite){const result=await api('/organizations/invitations/accept',{token:invite});
        await api('/organizations/switch',{organization_id:result.organization_id});}
      location.replace('/app/');
    }catch(err){setError(err.message);setBusy(false);}
  }
  return <><p className="login-lead">Your evaluation lab. Your team. Your evidence.</p>
    {authenticated?<><button className="auth-primary" disabled={busy||!ready} onClick={enter}>{busy?'Opening your workspace…':'Continue to workspace →'}</button>
      <button className="auth-secondary" disabled={!ready||busy||!passkeyEnabled} onClick={()=>void beginPasskey(()=>linkPasskey({name:'Ghost Trials'}))}>🔑 Create passkey for this account</button>
      <button className="auth-secondary" disabled={busy} onClick={()=>logout()}>Use a different account</button></>:
      <><button className="auth-primary" disabled={!ready||busy||!methods.includes('email')} onClick={()=>{setError('');login({loginMethods:['email']});}}><span aria-hidden="true">✉</span> Continue with email</button>
      <div className="auth-divider"><span>or</span></div><button className="auth-secondary" disabled={!ready||busy||!methods.includes('google')} onClick={()=>{setError('');login({loginMethods:['google']});}}><span className="google-symbol" aria-hidden="true">G</span> Continue with Google</button>
      <button className="auth-secondary" disabled={!ready||busy||passkeyBusy||!passkeyEnabled} onClick={()=>void beginPasskey(loginWithPasskey)}>🔑 Sign in with passkey</button>
      <button className="auth-secondary" disabled={!ready||busy||passkeyBusy||!passkeySignupEnabled} onClick={()=>void beginPasskey(signupWithPasskey)}>Create account with passkey</button>
      <p className="auth-note auth-passkey-help">Already have an email or Google account? Sign in first, then use “Create passkey for this account” to keep the same workspace.</p>
      {!methods.includes('google')&&<p className="auth-note">Google sign-in is awaiting activation by this app’s administrator in Privy.</p>}</>}
    {!passkeyEnabled&&<p className="auth-note">Passkeys are awaiting activation by this app’s administrator in Privy.</p>}
    {passkeyEnabled&&!authenticated&&!passkeySignupEnabled&&<p className="auth-note">New-account passkeys are not enabled in Privy yet. Sign in with email or Google to add a passkey to your account.</p>}
    {passkeyNotice&&<p className="auth-success" role="status">{passkeyNotice}</p>}
    {error&&<p className="auth-error" role="alert">{error}</p>}
    {!ready&&<p role="status">Connecting to secure sign-in…</p>}
    <p className="auth-note">{location.pathname==='/auth/invite'?'Sign in, then continue to accept your private team invitation.':'New accounts get an isolated workspace. Paid execution is disabled until an operator assigns a budget.'}</p></>;
}
async function start(){
  const root=createRoot(document.getElementById('privy-login'));
  try{
    const config=await api('/auth/config');
    document.getElementById('private-team').hidden=!config.private_team_enabled;
    document.getElementById('demo-link').hidden=!config.demo_enabled;
    if(config.auth_provider==='dynamic'){
      if(!config.dynamic_environment_id){root.render(<p className="auth-note">Dynamic sign-in is not configured on this deployment.</p>);return;}
      const {renderDynamic}=await import('./dynamic_auth.jsx');
      renderDynamic(root,config,api);
      return;
    }
    if(!config.privy_configured){root.render(<p className="auth-note">Customer sign-in is not configured on this deployment. No credentials are collected here.</p>);return;}
    root.render(<PrivyProvider appId={config.app_id} {...(config.client_id?{clientId:config.client_id}:{})}
      config={{loginMethods:['email','google','passkey'],appearance:{theme:'dark',accentColor:'#FF7A32',logo:'/assets/ghost-mark.svg',showWalletLoginFirst:false},
      embeddedWallets:{ethereum:{createOnLogin:'off'},solana:{createOnLogin:'off'}}}}><SignIn methods={config.methods} passkeySignupEnabled={config.passkey_signup_enabled}/></PrivyProvider>);
  }catch(error){root.render(<p className="auth-error" role="alert">{error.message}</p>);}
}
start();
