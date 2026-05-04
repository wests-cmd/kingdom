def setup():
    print("KINGDOM v26 INITIALIZATION")

    role = input("System role (commander/knight/both): ")

    control_level = int(input("Control Level (1-5): "))

    ai_mode = input("AI integration (none/ollama/claude/openclaw/jcode/mix): ")

    execution_mode = input("Execution mode (local/mix/cloud): ")

    print("\nInitializing Kingdom with:")
    print(role, control_level, ai_mode, execution_mode)

    return {
        "role": role,
        "control_level": control_level,
        "ai_mode": ai_mode,
        "execution_mode": execution_mode
    }
