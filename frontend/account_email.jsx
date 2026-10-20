import React from 'react';
import {createRoot} from 'react-dom/client';
import {PrivyProvider,usePrivy} from '@privy-io/react-auth';

function SignedInEmail({subject}){
  const {ready,authenticated,user}=usePrivy();
  if(!ready)return 'Loading your sign-in email…';
  if(!authenticated||user?.id!==subject)return 'Sign-in email unavailable for this session.';
  const email=user.email?.address||user.google?.email||user.apple?.email;
  return email||'No email is linked to this account.';
}

export async function mountAccountEmail(node,subject){
  try{
    const response=await fetch('/auth/config',{credentials:'same-origin'});
    if(!response.ok)throw new Error('Identity configuration unavailable');
    const config=await response.json();
    if(!node.isConnected||config.auth_provider!=='privy'||!config.app_id){
      if(node.isConnected)node.textContent='Sign-in email unavailable.';
      return;
    }
    const root=createRoot(node);
    const observer=new MutationObserver(()=>{
      if(!node.isConnected){observer.disconnect();root.unmount();}
    });
    observer.observe(document.getElementById('content'),{childList:true,subtree:true});
    root.render(<PrivyProvider appId={config.app_id} {...(config.client_id?{clientId:config.client_id}:{})}
      config={{loginMethods:config.methods||[],embeddedWallets:{ethereum:{createOnLogin:'off'},solana:{createOnLogin:'off'}}}}>
      <SignedInEmail subject={subject}/>
    </PrivyProvider>);
  }catch{
    if(node.isConnected)node.textContent='Sign-in email unavailable.';
  }
}
