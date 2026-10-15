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
  const emailEnabled=methods.includes('email');
  const googleEnabled=methods.includes('google');
  return <><p className="login-lead">Continue to your private evaluation workspace.</p>
    {authenticated?<><button className="auth-primary" disabled={busy||!ready} onClick={enter}>{busy?'Opening your workspace…':'Continue to workspace →'}</button>
      {passkeyEnabled&&<button className="auth-secondary" disabled={!ready||busy} onClick={()=>void beginPasskey(()=>linkPasskey({name:'Ghost Trials'}))}>Create a passkey for this account</button>}
      <button className="auth-text-button" disabled={busy} onClick={()=>logout()}>Use a different account</button></>:
      <div className="auth-methods">
        {emailEnabled&&<button className="auth-primary" disabled={!ready||busy} onClick={()=>{setError('');login({loginMethods:['email']});}}><span className="auth-method-icon" aria-hidden="true">✉</span><span>Continue with email</span><span className="auth-method-arrow" aria-hidden="true">↗</span></button>}
        {googleEnabled&&<button className={emailEnabled?'auth-secondary':'auth-primary'} disabled={!ready||busy} onClick={()=>{setError('');login({loginMethods:['google']});}}><span className="google-symbol" aria-hidden="true">G</span><span>Continue with Google</span><span className="auth-method-arrow" aria-hidden="true">↗</span></button>}
        {passkeyEnabled&&<button className={emailEnabled||googleEnabled?'auth-secondary':'auth-primary'} disabled={!ready||busy||passkeyBusy} onClick={()=>void beginPasskey(loginWithPasskey)}><span className="auth-method-icon" aria-hidden="true">⌁</span><span>Sign in with passkey</span><span className="auth-method-arrow" aria-hidden="true">↗</span></button>}
        {passkeyEnabled&&passkeySignupEnabled&&<button className="auth-text-button" disabled={!ready||busy||passkeyBusy} onClick={()=>void beginPasskey(signupWithPasskey)}>New here? Create a passkey account</button>}
        {!methods.length&&<p className="auth-error" role="alert">Sign-in is temporarily unavailable. Please try again later.</p>}
      </div>}
    {passkeyNotice&&<p className="auth-success" role="status">{passkeyNotice}</p>}
    {error&&<p className="auth-error" role="alert">{error}</p>}
    {!ready&&<p role="status">Connecting to secure sign-in…</p>}
    <p className="auth-note">{location.pathname==='/auth/invite'?'Continue to accept your team invitation.':'New to Ghost Trials? Continue with an available method to create your account.'}</p></>;
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
    if(!config.privy_configured){root.render(<p className="auth-error" role="alert">Sign-in is not configured on this deployment. No credentials are collected here.</p>);return;}
    const methods=Array.isArray(config.methods)?config.methods.filter(method=>['email','google','passkey'].includes(method)):[];
    if(!methods.length){root.render(<p className="auth-error" role="alert">Sign-in is temporarily unavailable. Please try again later.</p>);return;}
    root.render(<PrivyProvider appId={config.app_id} {...(config.client_id?{clientId:config.client_id}:{})}
      config={{loginMethods:methods,appearance:{theme:'light',accentColor:'#DB511B',logo:'/assets/ghost-mark.svg',showWalletLoginFirst:false},
      embeddedWallets:{ethereum:{createOnLogin:'off'},solana:{createOnLogin:'off'}}}}><SignIn methods={methods} passkeySignupEnabled={config.passkey_signup_enabled===true}/></PrivyProvider>);
  }catch(error){root.render(<p className="auth-error" role="alert">{error.message}</p>);}
}
start();
