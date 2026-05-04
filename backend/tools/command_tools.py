import asyncio
import subprocess
from typing import Any
from tools.base import BaseTool


class RunCommandTool(BaseTool):
    name = "run_command"
    description = "Execute a shell command on the local system and return stdout/stderr. Use for system operations like checking processes, running scripts, etc. Timeout is 30 seconds."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command. Optional.",
            },
        },
        "required": ["command"],
    }

    async def execute(self, command: str, cwd: str | None = None, **kwargs) -> dict[str, Any]:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                shell=True,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            except asyncio.TimeoutError:
                proc.kill()
                return {"success": False, "output": "Command timed out after 30 seconds."}

            output_parts = []
            if stdout:
                decoded = stdout.decode("utf-8", errors="replace").strip()
                if decoded:
                    output_parts.append(decoded)
            if stderr:
                decoded = stderr.decode("utf-8", errors="replace").strip()
                if decoded:
                    output_parts.append(f"[stderr] {decoded}")

            output = "\n".join(output_parts) if output_parts else "(no output)"
            # Truncate very long outputs
            if len(output) > 10_000:
                output = output[:10_000] + "\n... (truncated)"

            return {
                "success": proc.returncode == 0,
                "output": f"Exit code: {proc.returncode}\n{output}",
            }
        except Exception as e:
            return {"success": False, "output": str(e)}
