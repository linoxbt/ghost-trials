"""Content Security Policy shared by the backend pages and the Netlify build (no third-party imports)."""

# Origins follow Privy's published CSP guidance for its React SDK (email sign-in, no external wallets).
PAGE_CSP = ("default-src 'self'; script-src 'self' https://challenges.cloudflare.com; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; "
            "connect-src 'self' https://auth.privy.io wss://relay.walletconnect.com wss://relay.walletconnect.org "
            "https://*.rpc.privy.systems https://explorer-api.walletconnect.com; "
            "frame-src https://auth.privy.io https://verify.walletconnect.com https://verify.walletconnect.org "
            "https://challenges.cloudflare.com; child-src https://auth.privy.io https://verify.walletconnect.com "
            "https://verify.walletconnect.org; worker-src 'self' blob:; media-src 'self' blob:; manifest-src 'self'; "
            "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'; report-uri /csp-report")
