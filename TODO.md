# Implementing a new tool

1. Create a new tool in [tools](./pr_agent/tools/)
    - It will be called by the cli via the run function, which should match
    - the tool class should follow the same setup as the other tools, see
      their init methods.
2. Hook up in [pr-agent](./pr_agent/agent/pr_agent.py)
    - add to COMMANDS
3. 