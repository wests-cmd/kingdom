class PartialRepair:

    def repair(self, component):

        return {
            "component": component,
            "repaired": False,
            "status": "unsupported",
            "reason": "No repair was executed or verified. Use the owner-approved operational recovery controller."
        }
