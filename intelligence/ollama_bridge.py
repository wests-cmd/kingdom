import subprocess

def run_model(prompt, model="llama3"):
    result = subprocess.run(
        ["ollama", "run", model, prompt],
        capture_output=True,
        text=True
    )
    return result.stdout
