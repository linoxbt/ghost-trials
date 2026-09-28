import React, {useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {PrivyProvider,usePrivy} from '@privy-io/react-auth';

async function api(path,body){
  const response=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',
    headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
  const data=await response.json();
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Unable to complete sign-in. Please try again.');
  return data;
}
function SignIn({methods}){
  const {ready,authenticated,login,getAccessToken,logout}=usePrivy();
  const [error,setError]=useState(''),[busy,setBusy]=useState(false);
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
      <button className="auth-secondary" disabled={busy} onClick={()=>logout()}>Use a different account</button></>:
      <><button className="auth-primary" disabled={!ready||busy||!methods.includes('email')} onClick={()=>{setError('');login({loginMethods:['email']});}}><span aria-hidden="true">✉</span> Continue with email</button>
      <div className="auth-divider"><span>or</span></div><button className="auth-secondary" disabled={!ready||busy||!methods.includes('google')} onClick={()=>{setError('');login({loginMethods:['google']});}}><span className="google-symbol" aria-hidden="true">G</span> Continue with Google</button>
      {!methods.includes('google')&&<p className="auth-note">Google sign-in is awaiting activation by this app’s administrator in Privy.</p>}</>}
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
    if(!config.privy_configured){root.render(<p className="auth-note">Customer sign-in is not configured on this deployment. No credentials are collected here.</p>);return;}
    root.render(<PrivyProvider appId={config.app_id} {...(config.client_id?{clientId:config.client_id}:{})}
      config={{loginMethods:['email','google'],appearance:{theme:'dark',accentColor:'#FF7A32',logo:'/assets/ghost-mark.svg',showWalletLoginFirst:false},
      embeddedWallets:{ethereum:{createOnLogin:'off'},solana:{createOnLogin:'off'}}}}><SignIn methods={config.methods}/></PrivyProvider>);
  }catch(error){root.render(<p className="auth-error" role="alert">{error.message}</p>);}
}
start();
