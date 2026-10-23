// Old shareable links used /#/<route>; the workspace now lives under /app/.
if(location.hash.startsWith('#/'))location.replace('/app/'+location.hash);
