// Where the workspace sends people back after sign-in, and how a sign-out reaches the identity provider.
const params=()=>new URLSearchParams(location.search);

// Only workspace hash routes are accepted, so ?next= cannot become an open redirect.
export function destination(){
  if(params().get('manage')==='passkey')return '/app/#/account';
  // ?next= from the workspace, or the fragment a server redirect from /app/#/route carries along.
  const next=params().get('next')||(location.pathname==='/auth/login'?location.hash:'');
  return /^#\/[\w\-./?=&%]{0,200}$/.test(next)?'/app/'+next:'/app/';
}

export function signedOut(){return params().get('signed_out')==='1';}

// Drop the flag once the provider session has been ended, so a reload does not repeat it.
export function clearSignedOut(){
  const query=params();query.delete('signed_out');
  history.replaceState(null,'',location.pathname+(query.size?'?'+query:'')+location.hash);
}
