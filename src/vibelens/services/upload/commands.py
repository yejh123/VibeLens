"""Platform-specific CLI commands for zipping agent data directories.

Each agent CLI stores conversation data in a different location.
This module provides the shell commands users run to create the
zip archives that VibeLens can ingest via the upload endpoint.
"""

from fastapi import HTTPException

from vibelens.models.enums import AgentType

UPLOAD_COMMANDS: dict[str, dict[str, dict[str, str]]] = {
    AgentType.CLAUDE_CODE: {
        "macos": {
            "command": (
                "cd ~/.claude && zip -r ~/Desktop/claude-data.zip projects/"
                " -x '**/._*' '**/__MACOSX/*'"
            ),
            "description": "Output: ~/Desktop/claude-data.zip",
        },
        "linux": {
            "command": "cd ~/.claude && zip -r ~/Desktop/claude-data.zip projects/",
            "description": "Output: ~/Desktop/claude-data.zip",
        },
        "windows": {
            "command": (
                "cd $env:USERPROFILE\\.claude; Compress-Archive -Path projects\\*"
                " -DestinationPath $env:USERPROFILE\\Desktop\\claude-data.zip"
            ),
            "description": "Output: Desktop\\claude-data.zip",
        },
    },
    AgentType.CODEX: {
        "macos": {
            "command": (
                "cd ~/.codex && zip -r ~/Desktop/codex-data.zip sessions/"
                " -x '**/._*' '**/__MACOSX/*'"
            ),
            "description": "Output: ~/Desktop/codex-data.zip",
        },
        "linux": {
            "command": "cd ~/.codex && zip -r ~/Desktop/codex-data.zip sessions/",
            "description": "Output: ~/Desktop/codex-data.zip",
        },
        "windows": {
            "command": (
                "cd $env:USERPROFILE\\.codex; Compress-Archive -Path sessions\\*"
                " -DestinationPath $env:USERPROFILE\\Desktop\\codex-data.zip"
            ),
            "description": "Output: Desktop\\codex-data.zip",
        },
    },
    AgentType.GEMINI: {
        "macos": {
            "command": (
                "cd ~/.gemini && zip -r ~/Desktop/gemini-data.zip tmp/"
                " -i '*.json' -i '.project_root'"
            ),
            "description": "Output: ~/Desktop/gemini-data.zip",
        },
        "linux": {
            "command": (
                "cd ~/.gemini && zip -r ~/Desktop/gemini-data.zip tmp/"
                " -i '*.json' -i '.project_root'"
            ),
            "description": "Output: ~/Desktop/gemini-data.zip",
        },
        "windows": {
            "command": (
                "cd $env:USERPROFILE\\.gemini; Compress-Archive -Path tmp\\*"
                " -DestinationPath $env:USERPROFILE\\Desktop\\gemini-data.zip"
            ),
            "description": "Output: Desktop\\gemini-data.zip",
        },
    },
    AgentType.CLAUDE_CODE_WEB: {
        "macos": {
            "command": "# Export from claude.ai > Settings > Export Data",
            "description": "Upload the zip downloaded from claude.ai",
        },
        "linux": {
            "command": "# Export from claude.ai > Settings > Export Data",
            "description": "Upload the zip downloaded from claude.ai",
        },
        "windows": {
            "command": "# Export from claude.ai > Settings > Export Data",
            "description": "Upload the zip downloaded from claude.ai",
        },
    },
}


def get_upload_command(agent_type: str, os_platform: str) -> dict:
    """Look up the CLI command for zipping an agent's data directory.

    Args:
        agent_type: Agent CLI identifier (claude_code, codex, gemini).
        os_platform: Operating system (macos, linux, windows).

    Returns:
        Dict with 'command' and 'description' keys.

    Raises:
        HTTPException: If agent_type or os_platform is invalid.
    """
    try:
        agent = AgentType(agent_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown agent_type: {agent_type}") from None

    platform_commands = UPLOAD_COMMANDS.get(agent)
    if not platform_commands:
        raise HTTPException(status_code=400, detail=f"No commands for agent: {agent}")

    result = platform_commands.get(os_platform)
    if not result:
        raise HTTPException(status_code=400, detail=f"Unknown os_platform: {os_platform}")
    return result
