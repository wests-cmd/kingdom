import time
import traceback
from typing import Any, Callable, Dict, Optional
from backend.extensions.models import ExtensionInstance, ExtensionTrustState
from backend.extensions.registry import ExtensionRegistry


class SandboxExecutionError(Exception):
    pass


class ExtensionSandbox:

    def __init__(self, registry: ExtensionRegistry, max_error_threshold: int = 3):
        self.registry = registry
        self.max_error_threshold = max_error_threshold

    def execute_in_sandbox(
        self,
        extension_id: str,
        func: Callable[..., Any],
        *args,
        **kwargs
    ) -> Any:
        instance = self.registry.get_extension(extension_id)
        if not instance:
            raise SandboxExecutionError(f"Extension '{extension_id}' is not registered.")

        if instance.state != ExtensionTrustState.ENABLED:
            raise SandboxExecutionError(
                f"Extension '{extension_id}' cannot execute. Current state is '{instance.state}' (must be ENABLED)."
            )

        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            instance.error_count += 1
            instance.last_error = f"{type(e).__name__}: {str(e)}"

            # Quarantine if error threshold exceeded
            if instance.error_count >= self.max_error_threshold:
                self.registry.quarantine_extension(
                    extension_id,
                    reason=f"Exceeded max sandbox error threshold ({instance.error_count}/{self.max_error_threshold})"
                )

            raise SandboxExecutionError(f"Sandbox caught exception in extension '{extension_id}': {str(e)}") from e
