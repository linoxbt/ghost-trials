"""Content Security Policy shared by the backend pages and the Netlify build (no third-party imports)."""

# Identity-provider origins. Privy's follow its published CSP guidance for the React SDK (email sign-in,
# no external wallets); Dynamic's cover its API and embedded widget hosts (not yet browser-verified).
_PROVIDER_ORIGINS = {
    "privy": {"script": "https://challenges.cloudflare.com",
              "connect": "https://auth.privy.io wss://relay.walletconnect.com wss://relay.walletconnect.org "
                         "https://*.rpc.privy.systems https://explorer-api.walletconnect.com",
              "frame": "https://auth.privy.io https://verify.walletconnect.com https://verify.walletconnect.org "
                       "https://challenges.cloudflare.com",
              "img": ""},
    "dynamic": {"script": "", "connect": "https://*.dynamicauth.com https://*.dynamic.xyz",
                "frame": "https://*.dynamicauth.com https://*.dynamic.xyz",
                "img": "https://*.dynamicauth.com https://*.dynamic.xyz"},
}


def page_csp(provider: str = "privy") -> str:
    origins = _PROVIDER_ORIGINS.get(provider, _PROVIDER_ORIGINS["privy"])

    def allow(base, extra):
        return f"{base} {extra}".strip()

    own = "'self'"
    # 'self' frames are the workspace's own evidence previews (/artifacts/<id>/preview); Google Fonts
    # serves the site typography.
    return (f"default-src {own}; script-src {allow(own, origins['script'])}; "
            f"style-src {own} 'unsafe-inline' https://fonts.googleapis.com; "
            f"img-src {allow(own + ' data: blob:', origins['img'])}; font-src {own} data: https://fonts.gstatic.com; "
            f"connect-src {allow(own, origins['connect'])}; frame-src {allow(own, origins['frame'])}; "
            f"child-src {allow(own, origins['frame'])}; worker-src {own} blob:; media-src {own} blob:; "
            f"manifest-src {own}; frame-ancestors 'none'; object-src 'none'; base-uri {own}; form-action {own}; "
            "report-uri /csp-report")


PAGE_CSP = page_csp("privy")
