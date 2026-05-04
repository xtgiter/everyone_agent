"""
Python eval tool — execute Python code in a sandboxed subprocess.
"""

import asyncio
import tempfile
import os
from typing import Any
from tools.base import BaseTool


class PythonEvalTool(BaseTool):
    name = "python_eval"
    description = "Execute Python code and return the output. Runs in a separate process with a 30-second timeout. Use for calculations, data processing, quick scripts, etc."
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute. Use print() to output results.",
            },
        },
        "required": ["code"],
    }

    async def execute(self, code: str, **kwargs) -> dict[str, Any]:
        # Write code to a temp file and execute it
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(code)
                tmp_path = f.name

            proc = await asyncio.create_subprocess_exec(
                'python', tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            except asyncio.TimeoutError:
                proc.kill()
                return {"success": False, "output": "Execution timed out after 30 seconds."}
            finally:
                os.unlink(tmp_path)

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
            if len(output) > 10_000:
                output = output[:10_000] + "\n... (truncated)"

            return {
                "success": proc.returncode == 0,
                "output": output,
            }
        except Exception as e:
            return {"success": False, "output": str(e)}
