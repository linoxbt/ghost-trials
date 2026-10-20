import pytest

from ghost_trials.config import Settings
from ghost_trials.durable import DurableStore
from ghost_trials.security import AccessControl


def test_direct_server_import_requires_explicit_auth_or_local_dev(tmp_path):
    store = DurableStore(tmp_path / "auth.sqlite3")
    settings = Settings(_env_file=None, ghost_unauthenticated_local_dev=False,
                        ghost_admin_token=None, ghost_operator_token=None, ghost_viewer_token=None,
                        privy_app_id=None, dynamic_environment_id=None)
    with pytest.raises(ValueError, match="Configure individual authentication"):
        AccessControl(settings, store)


def test_unauthenticated_dev_cannot_be_public(tmp_path):
    store = DurableStore(tmp_path / "auth.sqlite3")
    settings = Settings(_env_file=None, ghost_unauthenticated_local_dev=True,
                        ghost_public_deployment=True, ghost_customer_auth_required=True,
                        privy_app_id="test-app", ghost_allowed_origins="https://example.com")
    with pytest.raises(ValueError, match="Unauthenticated development mode cannot run"):
        AccessControl(settings, store)
