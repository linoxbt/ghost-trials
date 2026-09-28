import {build} from 'esbuild';
import {resolve} from 'node:path';
const decoderBridge=resolve('frontend/decode-uri-component.cjs');
await build({entryPoints:['frontend/auth.jsx'],bundle:true,splitting:true,format:'esm',
  outdir:'static/auth',entryNames:'login',chunkNames:'chunks/[name]-[hash]',minify:true,
  sourcemap:false,target:['es2022'],define:{'process.env.NODE_ENV':'"production"'},
  legalComments:'external',plugins:[{name:'legacy-decoder-interop',setup(build){
    build.onResolve({filter:/^decode-uri-component$/},args=>
      args.kind==='require-call'&&args.importer!==decoderBridge?{path:decoderBridge}:undefined);
  }}]});
