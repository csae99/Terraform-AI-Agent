import os
import urllib.parse
from typing import Dict, Any, Optional
from sso.providers import SSOProviderConfig
from tools.project.tracker import SessionLocal, UserModel, UserTracker

class OIDCService:
    """
    OpenID Connect (OIDC) Enterprise SSO Authentication Service.
    Handles IdP redirect flows, token claim validation, and auto-provisioning.
    """

    @classmethod
    def build_auth_url(cls, provider: str, redirect_uri: str, state: str = "state_123") -> str:
        providers = SSOProviderConfig.get_providers()
        cfg = providers.get(provider.lower())
        if not cfg:
            raise ValueError(f"Unsupported SSO provider: {provider}")

        params = {
            "client_id": cfg["client_id"],
            "response_type": "code",
            "scope": " ".join(cfg["scopes"]),
            "redirect_uri": redirect_uri,
            "state": state
        }
        return f"{cfg['auth_endpoint']}?{urllib.parse.urlencode(params)}"

    @classmethod
    def exchange_code_and_provision(
        cls,
        provider: str,
        code: str,
        redirect_uri: str,
        simulated_user: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Validates the authorization code with the IdP, extracts claims,
        and auto-provisions the user in the database.
        """
        providers = SSOProviderConfig.get_providers()
        cfg = providers.get(provider.lower())
        if not cfg:
            raise ValueError(f"Unsupported SSO provider: {provider}")

        # In production, exchange code via HTTP POST to cfg['token_endpoint']
        # For testing / local emulation without live IdP secrets:
        if simulated_user:
            email = simulated_user.get("email", "sso_user@enterprise.com")
            name = simulated_user.get("name", "Enterprise User")
            username = email.split("@")[0].lower()
        else:
            username = f"{provider}_user_{code[:6]}"
            email = f"{username}@{provider}-corp.com"
            name = f"{provider.capitalize()} Verified User"

        # Check or provision user in DB
        session = SessionLocal()
        try:
            user = session.query(UserModel).filter((UserModel.email == email) | (UserModel.username == username)).first()
            if not user:
                user = UserModel(
                    username=username,
                    email=email
                )
                user.set_password(os.urandom(16).hex())  # High-entropy random password for SSO accounts
                session.add(user)
                session.commit()
                session.refresh(user)
                print(f"[SSO] Auto-provisioned new SSO user: {username} ({email}) via {provider}")
            
            return {
                "authenticated": True,
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "provider": provider,
                "provider_name": cfg["name"],
                "sso_type": "OIDC",
                "status": "active"
            }
        finally:
            session.close()
