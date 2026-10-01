"""Public product identity and Centipede API compatibility metadata.

The Kingdom release SemVer remains sourced from ``backend.state.STATE``. These
identifiers describe the separately versioned runtime product and wire
contract; they do not change Kingdom's cluster RPC protocol identifier.
"""

from __future__ import annotations

KINGDOM_PRODUCT_VERSION = "v1TAS"
CENTIPEDE_API_CONTRACT_VERSION = "1.4.0"
CENTIPEDE_PROTOCOL = {"major": 1, "minor": 4}
