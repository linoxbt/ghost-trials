from scripts import build_netlify


def test_netlify_build_proxies_every_workspace_collection(tmp_path, monkeypatch):
    monkeypatch.setattr(build_netlify, "TARGET", tmp_path / "site")
    monkeypatch.setattr(build_netlify, "ORIGIN", "https://backend.example.com")
    build_netlify.main()

    routes = (tmp_path / "site" / "_redirects").read_text().splitlines()
    for path in ("/account", "/trials", "/agent-trials", "/hunts", "/ghost-cases",
                 "/safety-score", "/health", "/capabilities", "/demonstration-readiness"):
        assert f"{path} https://backend.example.com{path} 200!" in routes
    assert "/agent-trials/* https://backend.example.com/agent-trials/:splat 200!" in routes
    assert (tmp_path / "site" / "assets" / "account.js").is_file()
