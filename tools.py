"""Tools for the chebupelka coding agent."""
import subprocess
import re
from pathlib import Path

import requests

USER_AGENT = "chebupelka/0.1"
MAX_FETCH_CHARS = 8000
MAX_GREP_MATCHES = 50
FETCH_TIMEOUT = 10


def run_bash(command: str) -> str:
    try:
        command_result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        out = command_result.stdout + (f"\nSTDERR:\n{command_result.stderr}" if command_result.stderr else "")
        return f"Exit code: {command_result.returncode}\n{out}"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 120s"


def read_file(path: str, offset: int | None = None, limit: int | None = None) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return f"Error: file '{path}' not found"
    except PermissionError:
        return f"Error: permission denied for '{path}'"
    except IsADirectoryError:
        return f"Error: '{path}' is a directory"
    except UnicodeDecodeError:
        return f"Error: cannot decode '{path}' as UTF-8"

    total = len(lines)
    if offset is not None:
        if offset < 0:
            return "Error: offset must be >= 0"
        if offset >= total:
            return f"Error: offset {offset} exceeds file length ({total} lines)"
        lines = lines[offset:]

    if limit is not None:
        if limit < 0:
            return "Error: limit must be >= 0"
        lines = lines[:limit]

    start = offset if offset is not None else 0
    return "".join(f"{start + i + 1}: {line}" for i, line in enumerate(lines))


def write_file(path: str, content: str) -> str:
    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
    except PermissionError:
        return f"Error: permission denied for '{path}'"
    except OSError as e:
        return f"Error writing '{path}': {e}"

    return f"Wrote {len(content)} chars, {content.count(chr(10))} lines to '{path}'"


def grep(pattern: str, include: str | None = None, path: str = ".") -> str:
    rg_path = None
    for candidate in ("rg",):
        try:
            subprocess.run([candidate, "--version"], capture_output=True, check=True)
            rg_path = candidate
            break
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    if rg_path:
        cmd = ["rg", "-n", "--color=never", "--no-heading"]
        if include:
            cmd += ["-g", include]
        cmd += [pattern, path]
    else:
        cmd = ["grep", "-rnI", "--color=never"]
        if include:
            cmd += ["--include", include]
        cmd += [pattern, path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return "Error: grep timed out after 30s"
    except FileNotFoundError:
        return "Error: neither rg (ripgrep) nor grep found on the system"

    if result.returncode not in (0, 1):
        return f"Error: grep failed\n{result.stderr}"

    lines = result.stdout.strip().split("\n")
    if not lines or lines == [""]:
        return "No matches found"

    if len(lines) > MAX_GREP_MATCHES:
        total_matches = len(lines)
        lines = lines[:MAX_GREP_MATCHES]
        lines.append(f"... ({total_matches} total matches, showing first {MAX_GREP_MATCHES})")

    return "\n".join(lines)


def web_fetch(url: str) -> str:
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT, headers={"User-Agent": USER_AGENT})
    except requests.exceptions.Timeout:
        return f"Error: request to '{url}' timed out after {FETCH_TIMEOUT}s"
    except requests.exceptions.ConnectionError as e:
        return f"Error: connection failed for '{url}': {e}"
    except requests.exceptions.InvalidURL:
        return f"Error: invalid URL '{url}'"
    except requests.exceptions.RequestException as e:
        return f"Error fetching '{url}': {e}"

    if resp.status_code != 200:
        return f"Error: HTTP {resp.status_code} for '{url}'"

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" in content_type:
        text = re.sub(r"<script[^>]*>.*?</script>", "", resp.text, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s{2,}", "\n", text).strip()
    elif "text/plain" in content_type or "application/json" in content_type:
        text = resp.text
    else:
        return f"Error: unsupported content type '{content_type}' for '{url}'"

    if len(text) > MAX_FETCH_CHARS:
        text = text[:MAX_FETCH_CHARS] + f"\n... (truncated at {MAX_FETCH_CHARS} chars)"

    return text


def web_search(query: str) -> str:
    results = []

    try:
        ddg = requests.get("https://api.duckduckgo.com/",
                           params={"q": query, "format": "json"},
                           timeout=FETCH_TIMEOUT, headers={"User-Agent": USER_AGENT})
        ddg.raise_for_status()
        data = ddg.json()

        abstract = data.get("Abstract", "").strip()
        if abstract:
            source = data.get("AbstractURL", "")
            results.append(f"[DDG] {abstract}" + (f"\n    Source: {source}" if source else ""))

        for topic in data.get("RelatedTopics", [])[:3]:
            text = (topic.get("Text") or "").strip()
            url = topic.get("FirstURL", "")
            if text:
                results.append(f"[DDG] {text}\n    URL: {url}")
    except Exception:
        pass

    try:
        wiki = requests.get("https://en.wikipedia.org/w/api.php",
                            params={"action": "query", "list": "search", "srsearch": query,
                                    "format": "json", "srlimit": 3},
                            timeout=FETCH_TIMEOUT, headers={"User-Agent": USER_AGENT})
        wiki.raise_for_status()
        data = wiki.json()
        for r in data.get("query", {}).get("search", []):
            snippet = re.sub(r"<[^>]+>", "", r.get("snippet", "")).strip()
            title = r.get("title", "")
            if snippet:
                results.append(f"[Wiki] {title}\n    {snippet}")
    except Exception:
        pass

    if not results:
        return "No search results found"

    return "\n\n".join(results[:5])


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a shell command and return the output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to execute."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file, optionally with a line range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file."},
                    "offset": {"type": "integer", "description": "Line number to start reading from (0-indexed)."},
                    "limit": {"type": "integer", "description": "Maximum number of lines to read."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file."},
                    "content": {"type": "string", "description": "The content to write to the file."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search file contents using a regex pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "The regex pattern to search for."},
                    "include": {"type": "string", "description": "File pattern to filter (e.g. '*.py')."},
                    "path": {"type": "string", "description": "Directory or file to search in. Defaults to '.'."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch content from a URL and return it as text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch."},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web and return the top results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                },
                "required": ["query"],
            },
        },
    },
]

TOOLS_MAP = {
    "bash": run_bash,
    "read_file": read_file,
    "write_file": write_file,
    "grep": grep,
    "web_fetch": web_fetch,
    "web_search": web_search,
}


def call_tool(name: str, arguments: dict) -> str:
    func = TOOLS_MAP.get(name)
    if not func:
        return f"Error: unknown tool '{name}'"
    try:
        return func(**arguments)
    except TypeError as e:
        return f"Error calling {name}: wrong arguments — {e}"
    except Exception as e:
        return f"Error calling {name}: {e}"
