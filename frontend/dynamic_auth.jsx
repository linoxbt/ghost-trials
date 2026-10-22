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
      if(invite){
        let result;
        try{result=await api('/organizations/invitations/accept',{token:invite});}
        catch(err){
          // The session already exists; drop the spent invitation so the next click opens the user's own workspace.
          history.replaceState(null,'','/auth/login');
          throw new Error(`${err.message} You are signed in: select Open workspace to continue, or ask for a new invitation.`);
        }
        await api('/organizations/switch',{organization_id:result.organization_id});}
      location.replace(new URLSearchParams(location.search).get('manage')==='passkey'?'/app/#/account':'/app/');
    }catch(err){setError(err.message);setBusy(false);}
  }

  return <>
    {!loggedIn&&<DynamicEmbeddedWidget background="none" />}
    {!loggedIn&&<button className="auth-secondary" disabled={!sdkHasLoaded||busy}
      onClick={()=>void runPasskey(signInWithPasskey)}>🔑 Sign in with passkey</button>}
    {loggedIn&&<><button className="auth-primary" disabled={busy} onClick={()=>void enter()}>
      {busy?'Opening workspace…':'Open workspace →'}</button>
      <button className="auth-secondary" disabled={busy} onClick={()=>void runPasskey(registerPasskey,
        'Passkey created for this account. You can use it to sign in next time.')}>🔑 Create passkey for this account</button></>}
    {notice&&<p className="auth-success" role="status">{notice}</p>}
    {error&&<p className="auth-error" role="alert">{error}</p>}
    {!sdkHasLoaded&&<p role="status">Connecting to secure sign-in…</p>}
    {location.pathname==='/auth/invite'&&<p className="auth-note">Sign in to accept your invitation.</p>}
  </>;
}

export function renderDynamic(root,config,api){
  root.render(<DynamicContextProvider settings={{environmentId:config.dynamic_environment_id,
    initialAuthenticationMode:'connect-and-sign',walletConnectors:[]}}><DynamicSignIn api={api}/></DynamicContextProvider>);
}
