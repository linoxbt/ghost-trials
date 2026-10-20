"""Tests never inherit a developer's real auth/provider configuration."""
import os

for name,value in {"PRIVY_APP_ID":"", "PRIVY_CLIENT_ID":"", "PRIVY_VERIFICATION_KEY":"",
    "GHOST_MODE":"local", "GHOST_SCENARIO_PROVIDER":"local", "GHOST_SIMULATOR_PROVIDER":"local",
    "GHOST_JUDGE_PROVIDER":"local", "GHOST_CUSTOMER_AUTH_REQUIRED":"false",
    "GHOST_UNAUTHENTICATED_LOCAL_DEV":"true",
    "GHOST_AGENT_MODEL_REVIEW_ENABLED":"false",
    "GHOST_ADMIN_TOKEN":"", "GHOST_OPERATOR_TOKEN":"", "GHOST_VIEWER_TOKEN":"",
    "COSMOS_API_STYLE":"nim", "COSMOS_NUM_FRAMES":"121", "COSMOS_BASE_URL":"",
    "COSMOS_API_KEY":"", "NVIDIA_API_KEY":"", "NEBIUS_API_KEY":"",
    "SCENARIO_REASONER_API_KEY":"", "ISAAC_JOB_ENDPOINT":"", "ISAAC_JOB_TOKEN":"",
    "GR00T_CHECKPOINT":"", "GR00T_CHECKPOINT_DIGEST":""}.items():
    os.environ[name]=value
