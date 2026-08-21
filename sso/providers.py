import os
from typing import Dict, Any

class SSOProviderConfig:
    """Enterprise SSO Identity Provider metadata and settings."""

    @staticmethod
    def get_providers() -> Dict[str, Dict[str, Any]]:
        return {
            "google": {
                "name": "Google Workspace",
                "issuer": "https://accounts.google.com",
                "auth_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_endpoint": "https://oauth2.googleapis.com/token",
                "userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo",
                "client_id": os.getenv("GOOGLE_SSO_CLIENT_ID", "mock-google-client-id"),
                "client_secret": os.getenv("GOOGLE_SSO_CLIENT_SECRET", "mock-google-secret"),
                "scopes": ["openid", "email", "profile"]
            },
            "azure_ad": {
                "name": "Microsoft Entra ID (Azure AD)",
                "issuer": "https://login.microsoftonline.com/common/v2.0",
                "auth_endpoint": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
                "token_endpoint": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                "userinfo_endpoint": "https://graph.microsoft.com/oidc/userinfo",
                "client_id": os.getenv("AZURE_SSO_CLIENT_ID", "mock-azure-client-id"),
                "client_secret": os.getenv("AZURE_SSO_CLIENT_SECRET", "mock-azure-secret"),
                "scopes": ["openid", "email", "profile", "User.Read"]
            },
            "okta": {
                "name": "Okta Enterprise",
                "issuer": os.getenv("OKTA_ISSUER", "https://dev-company.okta.com/oauth2/default"),
                "auth_endpoint": os.getenv("OKTA_AUTH_ENDPOINT", "https://dev-company.okta.com/oauth2/default/v1/authorize"),
                "token_endpoint": os.getenv("OKTA_TOKEN_ENDPOINT", "https://dev-company.okta.com/oauth2/default/v1/token"),
                "userinfo_endpoint": os.getenv("OKTA_USERINFO_ENDPOINT", "https://dev-company.okta.com/oauth2/default/v1/userinfo"),
                "client_id": os.getenv("OKTA_CLIENT_ID", "mock-okta-client-id"),
                "client_secret": os.getenv("OKTA_CLIENT_SECRET", "mock-okta-secret"),
                "scopes": ["openid", "email", "profile", "groups"]
            },
            "auth0": {
                "name": "Auth0 Enterprise",
                "issuer": os.getenv("AUTH0_ISSUER", "https://company.auth0.com/"),
                "auth_endpoint": os.getenv("AUTH0_AUTH_ENDPOINT", "https://company.auth0.com/authorize"),
                "token_endpoint": os.getenv("AUTH0_TOKEN_ENDPOINT", "https://company.auth0.com/oauth/token"),
                "userinfo_endpoint": os.getenv("AUTH0_USERINFO_ENDPOINT", "https://company.auth0.com/userinfo"),
                "client_id": os.getenv("AUTH0_CLIENT_ID", "mock-auth0-client-id"),
                "client_secret": os.getenv("AUTH0_CLIENT_SECRET", "mock-auth0-secret"),
                "scopes": ["openid", "email", "profile"]
            }
        }
