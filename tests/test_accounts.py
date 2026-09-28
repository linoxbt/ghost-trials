import asyncio
import time
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException

from ghost_trials.accounts import Accounts
from ghost_trials.config import Settings
from ghost_trials.durable import DurableStore
from ghost_trials.models import LiveEvent, TrialStatus
from ghost_trials.private_setup import prepare_team


def test_private_setup_preserves_credentials_and_disables_spending(tmp_path):
    directory=tmp_path/'private'
    report=prepare_team(directory,'testappid','lab.example.com','operator@example.com')
    assert report['compute_purchased'] is False
    config=(directory/'production.env').read_text()
    assert 'GHOST_LIVE_EXECUTION_ENABLED=false' in config
    assert 'GHOST_CUSTOMER_AUTH_REQUIRED=true' in config
    assert (directory/'production.env').stat().st_mode&0o777==0o600
    first=(directory/'access.env').read_bytes()
    assert not prepare_team(directory,'otherappid','lab.example.com','operator@example.com')['deployment_file_created']
    assert (directory/'access.env').read_bytes()==first
    assert (directory/'production.env').read_text()==config
    with pytest.raises(ValueError):
        prepare_team(directory,'testappid','lab.example.com\nEVIL=true','operator@example.com')


@pytest.fixture
def identities(monkeypatch,tmp_path):
    from ghost_trials.app import app,settings,access,store,pipeline
    key=ec.generate_private_key(ec.SECP256R1())
    public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    for name,value in {'privy_app_id':'testapp','privy_verification_key':public,'ghost_cookie_secure':False,
        'ghost_allowed_origins':'https://console.test','ghost_public_signup_enabled':True,
        'ghost_live_execution_enabled':False}.items():
        monkeypatch.setattr(settings,name,value)
    monkeypatch.setattr(access,'enabled',True)
    monkeypatch.setattr(access,'tokens',{'admin':'p'*48})
    monkeypatch.setattr(store,'path',tmp_path/'accounts.sqlite3')
    monkeypatch.setattr(store,'trials',{})
    monkeypatch.setattr(store,'scenarios',{})
    monkeypatch.setattr(settings,'ghost_artifact_root',tmp_path/'artifacts')
    monkeypatch.setattr(pipeline,'delay',0)
    def token(subject='alice',**changes):
        claims={'sub':'did:privy:'+subject,'iss':'privy.io','aud':'testapp','iat':int(time.time()),
            'exp':int(time.time())+3600,'sid':'test-session'}
        claims.update(changes)
        return jwt.encode(claims,key,algorithm='ES256')
    return app,access,store,settings,token


async def signin(client,token):
    response=await client.post('/auth/privy/session',json={'access_token':token},headers={'Origin':'https://console.test'})
    assert response.status_code==200,response.text
    assert 'HttpOnly' in response.headers['set-cookie']
    return response.json()['organization_id']


@pytest.mark.asyncio
async def test_verified_identity_and_revocable_session(identities):
    app,access,store,_,token=identities
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://test') as client:
        for invalid in [token(aud='other'),token(exp=int(time.time())-1),token(iss='attacker'),token(sub='admin')]:
            assert (await client.post('/auth/privy/session',json={'access_token':invalid},headers={'Origin':'https://console.test'})).status_code==401
        org=await signin(client,token())
        me=(await client.get('/auth/me')).json()
        assert me['organization_id']==org and me['authentication_kind']=='privy'
        assert (await client.get('/account')).json()['subject']=='did:privy:alice'
        stolen=client.cookies['ghost_session']
        with store.connect() as db:
            assert db.execute('SELECT digest FROM sessions').fetchone()[0]!=stolen
        assert (await client.post('/auth/logout',headers={'Origin':'https://console.test'})).status_code==200
        client.cookies.set('ghost_session',stolen)
        assert (await client.get('/trials')).status_code==401


@pytest.mark.asyncio
async def test_all_trial_reads_writes_media_and_idempotency_are_isolated(identities):
    app,access,store,settings,token=identities
    transport=httpx.ASGITransport(app)
    origin={'Origin':'https://console.test','Idempotency-Key':'shared-key'}
    body={'prompt':'A box falls into the walking robot path','seed':42}
    async with httpx.AsyncClient(transport=transport,base_url='http://test') as alice,httpx.AsyncClient(transport=transport,base_url='http://test') as bob:
        a=await signin(alice,token())
        b=await signin(bob,token('bob'))
        assert a!=b
        first=(await alice.post('/scenarios',json=body,headers=origin)).json()
        tid,sid=first['trial']['trial_id'],first['scenario']['scenario_id']
        assert first['trial']['organization_id']==a
        from ghost_trials.app import pipeline
        await pipeline.run(tid)
        assert store.scenarios[sid].organization_id==a
        root=settings.ghost_artifact_root/'trials'/tid
        root.mkdir(parents=True)
        (root/'telemetry.jsonl').write_text('private trace')
        assert (await alice.get(f'/generated/trials/{tid}/telemetry.jsonl')).status_code==200
        for path in [f'/trials/{tid}',f'/trials/{tid}/evidence',f'/trials/{tid}/reproducibility',f'/artifacts/{sid}/preview',
            f'/generated/trials/{tid}/telemetry.jsonl',f'/comparisons?baseline={tid}&candidate={tid}']:
            assert (await bob.get(path)).status_code==404,path
        for action in ['replay','cancel']:
            assert (await bob.post(f'/trials/{tid}/{action}',headers=origin)).status_code==404
        assert (await bob.get('/trials')).json()==[]
        assert (await bob.get('/safety-score')).json()['n_trials']==0
        assert (await bob.get('/benchmarks')).status_code==200
        assert (await bob.get('/demonstration-readiness')).json()['trial_ids']==[]
        exported=(await alice.get(f'/trials/{tid}/reproducibility')).json()
        assert exported['evidence']['evidence_class']=='synthetic_demo'
        assert exported['evidence']['score_eligible'] is False
        second=await bob.post('/scenarios',json=body,headers=origin)
        assert second.status_code==202
        assert second.json()['trial']['trial_id']!=tid
        assert (await alice.post('/scenarios',json=body,headers=origin)).json()['trial']['trial_id']==tid
        assert (await alice.get('/ops/audit')).status_code==403
        assert (await alice.put(f'/ops/organizations/{a}/budget',json={'limit_cents':500},headers=origin)).status_code==403
        # Symlink under an owned trial must not reveal a different workspace file.
        secret=settings.ghost_artifact_root/'secret.txt'
        secret.write_text('other workspace')
        (root/'link.txt').symlink_to(secret)
        assert (await alice.get(f'/generated/trials/{tid}/link.txt')).status_code==404


@pytest.mark.asyncio
async def test_invitations_roles_removal_and_cross_workspace_switch(identities):
    app,access,store,_,token=identities
    origin={'Origin':'https://console.test'}
    transport=httpx.ASGITransport(app)
    async with httpx.AsyncClient(transport=transport,base_url='http://test') as alice,httpx.AsyncClient(transport=transport,base_url='http://test') as bob:
        a=await signin(alice,token())
        await signin(bob,token('bob'))
        assert (await bob.post('/organizations/switch',json={'organization_id':a},headers=origin)).status_code==404
        invite=(await alice.post('/organizations/current/invitations',json={'role':'viewer'},headers=origin)).json()['invitation_token']
        assert (await bob.post('/organizations/invitations/accept',json={'token':invite},headers=origin)).status_code==200
        assert (await bob.post('/organizations/invitations/accept',json={'token':invite},headers=origin)).status_code==404
        assert (await bob.post('/organizations/switch',json={'organization_id':a},headers=origin)).status_code==200
        assert (await bob.get('/auth/me')).json()['role']=='viewer'
        assert (await bob.post('/scenarios',json={'prompt':'A falling box enters the path'},headers=origin)).status_code==403
        assert (await bob.post('/organizations/current/invitations',json={'role':'operator'},headers=origin)).status_code==403
        assert (await alice.patch('/organizations/current/members/did:privy:bob',json={'role':'operator'},headers=origin)).status_code==200
        assert (await bob.get('/auth/me')).json()['role']=='operator'
        assert (await alice.delete('/organizations/current/members/did:privy:alice',headers=origin)).status_code==409
        assert (await alice.delete('/organizations/current/members/did:privy:bob',headers=origin)).status_code==200
        assert (await bob.get('/trials')).status_code==401
        audit=(await alice.get('/organizations/current/audit')).json()
        assert all(r['subject']=='did:privy:alice' for r in audit if r['action']=='member_removed')


@pytest.mark.asyncio
async def test_budget_reservation_atomic_rollback_and_persistence(identities,monkeypatch):
    app,access,store,settings,token=identities
    transport=httpx.ASGITransport(app)
    origin={'Origin':'https://console.test'}
    async with httpx.AsyncClient(transport=transport,base_url='http://test') as client:
        org=await signin(client,token())
        monkeypatch.setattr(settings,'ghost_judge_provider','nebius')
        monkeypatch.setattr(settings,'ghost_live_execution_enabled',True)
        body={'prompt':'A box falls into the walking robot path'}
        assert (await client.post('/scenarios',json=body,headers=origin)).status_code==503
        monkeypatch.setattr(settings,'ghost_provider_spending_controls_confirmed',True)
        monkeypatch.setattr(settings,'ghost_platform_budget_cents',100)
        monkeypatch.setattr(settings,'ghost_live_job_reservation_cents',60)
        assert (await client.post('/scenarios',json=body,headers=origin)).status_code==402
        assert not store.trials
        access.accounts.allocate_budget(org,500)
        assert (await client.post('/scenarios',json=body,headers=origin)).status_code==202
        assert (await client.post('/scenarios',json=body,headers=origin)).status_code==402
        assert len(store.trials)==1
        assert access.accounts.budget(org)['used_cents']==60
        assert Accounts(DurableStore(store.path),settings).budget('platform')['used_cents']==60


@pytest.mark.asyncio
async def test_live_events_filtered_and_membership_revocation(identities):
    app,access,store,_,token=identities
    from ghost_trials.app import publish,subscribers,pipeline
    a_raw,a,_=access.accounts.start_session(access.accounts.verify(token()))
    b_raw,b,_=access.accounts.start_session(access.accounts.verify(token('bob')))
    from ghost_trials.models import ScenarioCreate
    scenario,trial=await pipeline.create(ScenarioCreate(prompt='A box falls into the walking path'),persist=False)
    scenario.organization_id=trial.organization_id=a.organization_id
    store.submit(scenario,trial)
    class Socket:
        def __init__(self,raw,principal):
            self.cookies={'ghost_session':raw};self.state=SimpleNamespace(principal=principal);self.events=[];self.closed=False
        async def send_json(self,event):self.events.append(event)
        async def close(self,code):self.closed=True
    sa,sb=Socket(a_raw,a),Socket(b_raw,b)
    subscribers.update([sa,sb])
    try:
        await publish(LiveEvent(trial_id=trial.trial_id,status=TrialStatus.QUEUED,message='queued'))
        assert len(sa.events)==1 and not sb.events
        access.accounts.revoke(a_raw)
        await publish(LiveEvent(trial_id=trial.trial_id,status=TrialStatus.DONE,message='done'))
        assert sa.closed and sa not in subscribers
    finally:
        subscribers.discard(sa);subscribers.discard(sb)
