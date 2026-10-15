import React, {useState} from 'react';
import {DynamicContextProvider,DynamicEmbeddedWidget,getAuthToken,useDynamicContext,useIsLoggedIn,
  useRegisterPasskey,useSignInWithPasskey} from '@dynamic-labs/sdk-react-core';

function DynamicSignIn({api}){
  const {sdkHasLoaded}=useDynamicContext();
  const loggedIn=useIsLoggedIn();
  const registerPasskey=useRegisterPasskey();
  const signInWithPasskey=useSignInWithPasskey();
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');

  async function runPasskey(action,successMessage){
    setBusy(true);setError('');setNotice('');
    try{
      await action();
      if(successMessage)setNotice(successMessage);
    }catch(err){setError(err instanceof Error?err.message:'Passkey request failed. Please try again.');}
    finally{setBusy(false);}
  }

  async function enter(){
    const access_token=getAuthToken();
    if(!access_token){setError('Please sign in again.');return;}
    setBusy(true);setError('');
    try{
      await api('/auth/dynamic/session',{access_token});
      const invite=location.pathname==='/auth/invite'?location.hash.slice(1):'';
      if(invite){const result=await api('/organizations/invitations/accept',{token:invite});
        await api('/organizations/switch',{organization_id:result.organization_id});}
      location.replace('/app/');
    }catch(err){setError(err.message);setBusy(false);}
  }

  return <><p className="login-lead">Your evaluation lab. Your team. Your evidence.</p>
    {!loggedIn&&<DynamicEmbeddedWidget background="none" />}
    {!loggedIn&&<><button className="auth-secondary" disabled={!sdkHasLoaded||busy}
      onClick={()=>void runPasskey(signInWithPasskey)}>🔑 Sign in with passkey</button>
      <p className="auth-note auth-passkey-help">To create a passkey, sign in with email or Google first. You can add one to your account before opening the workspace.</p></>}
    {loggedIn&&<><button className="auth-primary" disabled={busy} onClick={()=>void enter()}>
      {busy?'Opening your workspace…':'Continue to workspace →'}</button>
      <button className="auth-secondary" disabled={busy} onClick={()=>void runPasskey(registerPasskey,
        'Passkey created for this account. You can use it to sign in next time.')}>🔑 Create passkey for this account</button></>}
    {notice&&<p className="auth-success" role="status">{notice}</p>}
    {error&&<p className="auth-error" role="alert">{error}</p>}
    {!sdkHasLoaded&&<p role="status">Connecting to secure sign-in…</p>}
    <p className="auth-note">{location.pathname==='/auth/invite'?'Sign in, then continue to accept your private team invitation.':'New accounts get an isolated workspace. Paid execution is disabled until an operator assigns a budget.'}</p>
  </>;
}

export function renderDynamic(root,config,api){
  root.render(<DynamicContextProvider settings={{environmentId:config.dynamic_environment_id,
    initialAuthenticationMode:'connect-and-sign',walletConnectors:[]}}><DynamicSignIn api={api}/></DynamicContextProvider>);
}
