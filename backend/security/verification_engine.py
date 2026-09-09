import os
import time
from enum import Enum
from typing import Dict, Any, Optional, Callable
from pydantic import BaseModel, Field


class VerificationState(str, Enum):
    REQUESTED = "REQUESTED"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class VerificationRecord(BaseModel):
    action_id: str
    operation_type: str
    target_resource: str
    claimed_success: bool
    observed_state: VerificationState = VerificationState.UNKNOWN
    evidence_details: Dict[str, Any] = Field(default_factory=dict)
    verified_at: float = Field(default_factory=time.time)


class IndependentVerificationEngine:

    @staticmethod
    def verify_filesystem_write(filepath: str, expected_min_bytes: int = 1) -> VerificationRecord:
        action_id = f"fs_ver_{time.time_ns()}"
        if not os.path.exists(filepath):
            return VerificationRecord(
                action_id=action_id,
                operation_type="filesystem_write",
                target_resource=filepath,
                claimed_success=True,
                observed_state=VerificationState.FAILED,
                evidence_details={"error": "File does not exist on filesystem after write claim."}
            )

        actual_size = os.path.getsize(filepath)
        if actual_size < expected_min_bytes:
            return VerificationRecord(
                action_id=action_id,
                operation_type="filesystem_write",
                target_resource=filepath,
                claimed_success=True,
                observed_state=VerificationState.FAILED,
                evidence_details={"error": f"File size ({actual_size}b) is less than expected ({expected_min_bytes}b)."}
            )

        return VerificationRecord(
            action_id=action_id,
            operation_type="filesystem_write",
            target_resource=filepath,
            claimed_success=True,
            observed_state=VerificationState.VERIFIED,
            evidence_details={"actual_size_bytes": actual_size}
        )

    @staticmethod
    def verify_external_action(
        target_resource: str,
        claimed_success: bool,
        verifier_callback: Optional[Callable[[], bool]] = None
    ) -> VerificationRecord:
        action_id = f"ext_ver_{time.time_ns()}"
        if verifier_callback is None:
            # Cannot verify external action without independent callback -> UNKNOWN state
            return VerificationRecord(
                action_id=action_id,
                operation_type="external_action",
                target_resource=target_resource,
                claimed_success=claimed_success,
                observed_state=VerificationState.UNKNOWN,
                evidence_details={"warning": "Independent verifier absent; external state cannot be guaranteed."}
            )

        try:
            verified = verifier_callback()
            if verified:
                return VerificationRecord(
                    action_id=action_id,
                    operation_type="external_action",
                    target_resource=target_resource,
                    claimed_success=claimed_success,
                    observed_state=VerificationState.VERIFIED,
                    evidence_details={"verifier": "callback_succeeded"}
                )
            else:
                return VerificationRecord(
                    action_id=action_id,
                    operation_type="external_action",
                    target_resource=target_resource,
                    claimed_success=claimed_success,
                    observed_state=VerificationState.FAILED,
                    evidence_details={"verifier": "callback_returned_false"}
                )
        except Exception as e:
            return VerificationRecord(
                action_id=action_id,
                operation_type="external_action",
                target_resource=target_resource,
                claimed_success=claimed_success,
                observed_state=VerificationState.UNKNOWN,
                evidence_details={"verifier_exception": str(e)}
            )
