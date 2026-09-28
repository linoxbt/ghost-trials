"""Prepare a protected synthetic team deployment without purchasing infrastructure."""
import argparse
import json
import re
from pathlib import Path
from .access_setup import prepare_access
from .execution_setup import private_create


def prepare_team(directory, app_id, domain, email):
    if not re.fullmatch(r"[a-zA-Z0-9]{5,100}", app_id):
        raise ValueError("Provide a public Privy App ID")
    if len(domain)>253 or "." not in domain or any(not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", part) for part in domain.split(".")):
        raise ValueError("Provide a DNS hostname without a scheme or path")
    if not re.fullmatch(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63}", email):
        raise ValueError("Provide the certificate contact email")
    report=prepare_access(directory)
    path=directory/"production.env"
    if path.is_symlink():
        raise ValueError("Refusing symlinked deployment config")
    created=not path.exists()
    if created:
        values={"GHOST_MODE":"local","GHOST_SCENARIO_PROVIDER":"local","GHOST_SIMULATOR_PROVIDER":"local",
            "GHOST_JUDGE_PROVIDER":"local","PRIVY_APP_ID":app_id,"GHOST_CUSTOMER_AUTH_REQUIRED":"true",
            "GHOST_PUBLIC_SIGNUP_ENABLED":"true","GHOST_COOKIE_SECURE":"true","GHOST_ALLOWED_ORIGINS":"https://"+domain,
            "GHOST_DOMAIN":domain,"ACME_EMAIL":email,"GHOST_LIVE_EXECUTION_ENABLED":"false",
            "GHOST_PLATFORM_BUDGET_CENTS":"0","GHOST_LIVE_JOB_RESERVATION_CENTS":"0",
            "GHOST_PROVIDER_SPENDING_CONTROLS_CONFIRMED":"false"}
        private_create(path,"".join(f"{key}={value}\n" for key,value in values.items()))
    return {**report,"deployment_file":str(path),"deployment_file_created":created,
        "compute_purchased":False,"trial_evidence":"synthetic",
        "next_step":"Review configuration and DNS before starting secure.compose.yaml"}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory",type=Path,default=Path("deployment/private"))
    parser.add_argument("--privy-app-id",required=True)
    parser.add_argument("--domain",required=True)
    parser.add_argument("--email",required=True)
    args=parser.parse_args()
    print(json.dumps(prepare_team(args.directory,args.privy_app_id,args.domain,args.email)))


if __name__=="__main__":
    main()
