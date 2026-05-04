class ControlLevel:
    """
    JARVIS-style system authority levels
    """

    L1_OBSERVER = 1      # read-only insights
    L2_ASSIST = 2        # suggests actions
    L3_SEMI_AUTO = 3     # executes with approval
    L4_AUTO = 4          # autonomous execution
    L5_SYSTEM = 5        # full system control (self-modifying)
