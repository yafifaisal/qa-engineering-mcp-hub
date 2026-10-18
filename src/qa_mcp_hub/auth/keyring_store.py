import keyring


class KeyringStore:
    SERVICE = 'qa-engineering-mcp-hub'

    def get(self, credential_id: str) -> str | None:
        return keyring.get_password(self.SERVICE, credential_id)

    def set(self, credential_id: str, secret: str) -> None:
        if not secret:
            raise ValueError('Empty secret')
        keyring.set_password(self.SERVICE, credential_id, secret)

    def delete(self, credential_id: str) -> None:
        keyring.delete_password(self.SERVICE, credential_id)
