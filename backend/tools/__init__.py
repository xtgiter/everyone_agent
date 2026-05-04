from tools.registry import ToolRegistry, tool_registry
from tools.file_tools import ReadFileTool, WriteFileTool, ListDirectoryTool
from tools.command_tools import RunCommandTool
from tools.search_tools import WebSearchTool
from tools.memory_tools import ReadMemoryTool, UpdateMemoryTool, UpdateUserProfileTool
from tools.skill_tools import ListSkillsTool, ReadSkillTool, CreateSkillTool, UpdateSkillTool, DeleteSkillTool
from tools.grep_tool import GrepTool
from tools.url_tool import ReadUrlTool
from tools.python_tool import PythonEvalTool
from tools.edit_tool import EditFileTool
from tools.git_tools import GitStatusTool, GitDiffTool, GitCommitTool, GitLogTool
from tools.delegate_tools import ListAgentsTool, DelegateTaskTool, DelegateParallelTool, DelegateChainTool

# Register all tools
tool_registry.register(ReadFileTool())
tool_registry.register(WriteFileTool())
tool_registry.register(EditFileTool())
tool_registry.register(ListDirectoryTool())
tool_registry.register(GrepTool())
tool_registry.register(RunCommandTool())
tool_registry.register(PythonEvalTool())
tool_registry.register(WebSearchTool())
tool_registry.register(ReadUrlTool())
tool_registry.register(GitStatusTool())
tool_registry.register(GitDiffTool())
tool_registry.register(GitCommitTool())
tool_registry.register(GitLogTool())
tool_registry.register(ReadMemoryTool())
tool_registry.register(UpdateMemoryTool())
tool_registry.register(UpdateUserProfileTool())
tool_registry.register(ListSkillsTool())
tool_registry.register(ReadSkillTool())
tool_registry.register(CreateSkillTool())
tool_registry.register(UpdateSkillTool())
tool_registry.register(DeleteSkillTool())
tool_registry.register(ListAgentsTool())
tool_registry.register(DelegateTaskTool())
tool_registry.register(DelegateParallelTool())
tool_registry.register(DelegateChainTool())
