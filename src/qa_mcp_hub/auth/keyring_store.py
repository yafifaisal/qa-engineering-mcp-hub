"""Pre-existing operating-system keyring adapter retained for Milestone 01.

Purpose: Preserve narrow keyring operations pending policy integration.
Owning Milestone: 01
Status: SCAFFOLDED
Ownership: auth.keyring_store
Dependencies: The keyring package and the future credential-store policy boundary.
Expected tests: Backend isolation, empty-secret rejection, missing entries, deletion.

Implementation note: This pre-existing class is not imported or registered by
the Milestone 00 runtime and does not establish complete keyring integration.
"""

import keyring


class KeyringStore:
    """Pre-existing minimal keyring wrapper; runtime integration remains scaffolded."""

    SERVICE = "qa-engineering-mcp-hub"

    def get(self, credential_id: str) -> str | None:
        return keyring.get_password(self.SERVICE, credential_id)

    def set(self, credential_id: str, secret: str) -> None:
        if not secret:
            raise ValueError("Empty secret")
        keyring.set_password(self.SERVICE, credential_id, secret)

    def delete(self, credential_id: str) -> None:
        keyring.delete_password(self.SERVICE, credential_id)
