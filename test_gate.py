import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.agent import KlatAgent
from src.config import ensure_env, set_provider, set_model, set_reasoning

def main():
    project, location = ensure_env()
    set_provider("openrouter")
    set_model("inclusionai/ling-2.6-flash")
    set_reasoning("none")
    
    agent = KlatAgent(project, location)
    agent.reset()
    
    query = "Will you audit the tools module for any missing error handling?"
    print(f"User: {query}")
    agent.chat(query)

if __name__ == "__main__":
    main()
