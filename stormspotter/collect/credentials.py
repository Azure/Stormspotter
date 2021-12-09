from azure.core.credentials import AccessToken
from azure.identity.aio import AzureCliCredential
from azure.identity.aio._internal.get_token_mixin import GetTokenMixin
from typing import Optional, Any


class CachedAzureCliCredential(AzureCliCredential, GetTokenMixin):
    """An implementation of AzureCliCredential that stores the access token"""

    token = {}

    async def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:

        if not self.token.get(scopes[0]):
            self.token[scopes[0]] = await AzureCliCredential.get_token(
                self, *scopes, **kwargs
            )
        else:
            self.token[scopes[0]] = await GetTokenMixin.get_token(
                self, *scopes, **kwargs
            )

        return self.token.get(scopes[0])

    async def _acquire_token_silently(
        self, *scopes: str, **kwargs: Any
    ) -> Optional[AccessToken]:
        return self.token.get(scopes[0])

    async def _request_token(self, *scopes: str, **kwargs: Any) -> AccessToken:
        self.token[scopes[0]] = await AzureCliCredential.get_token(
            self, *scopes, **kwargs
        )
        return self.token.get(scopes[0])
