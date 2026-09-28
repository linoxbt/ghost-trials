// Preserve legacy CommonJS consumers while using the patched ESM decoder.
// esbuild bundles this interop bridge; no dependency source files are modified.
const decoder = require('decode-uri-component');
module.exports = decoder.default || decoder;
