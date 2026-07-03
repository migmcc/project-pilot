"""Static guard: the runtime package must perform no forbidden automation.

Parses ``src/`` with ``ast`` and rejects imports, calls, and action-like string
constants that would indicate process spawning, network access, or
VCS/release/install automation. Comments and docstrings are intentionally
ignored so ordinary documentation can mention tools without tripping the guard.
"""
import ast
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

FORBIDDEN_IMPORT_ROOTS = {
    "subprocess",
    "socket",
    "urllib",
    "http",
    "requests",
}

FORBIDDEN_CALLS = {
    "os.system",
    "os.popen",
    "subprocess.run",
    "subprocess.Popen",
}

FORBIDDEN_STRING_PHRASES = {
    "pip install",
    "git push",
    "git commit",
    "subprocess",
    "socket",
    "urllib",
    "http://",
    "https://",
}


def _import_root(name):
    return name.split(".", 1)[0]


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        if parent is None:
            return None
        return f"{parent}.{node.attr}"
    return None


def _docstring_node_ids(tree):
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.body:
                continue
            candidate = node.body[0]
            if (
                isinstance(candidate, ast.Expr)
                and isinstance(candidate.value, ast.Constant)
                and isinstance(candidate.value.value, str)
            ):
                ids.add(id(candidate.value))
    return ids


def scan_python_source(path, source):
    violations = []
    tree = ast.parse(source, filename=str(path))
    docstring_ids = _docstring_node_ids(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _import_root(alias.name)
                if root in FORBIDDEN_IMPORT_ROOTS:
                    violations.append(f"{path}:{node.lineno}: forbidden import {alias.name!r}")

        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            root = _import_root(node.module)
            if root in FORBIDDEN_IMPORT_ROOTS:
                violations.append(f"{path}:{node.lineno}: forbidden import from {node.module!r}")

        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in FORBIDDEN_CALLS:
                violations.append(f"{path}:{node.lineno}: forbidden call {name!r}")

        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstring_ids
        ):
            value = node.value.lower()
            for phrase in sorted(FORBIDDEN_STRING_PHRASES):
                if phrase in value:
                    violations.append(
                        f"{path}:{node.lineno}: forbidden string phrase {phrase!r}"
                    )

    return violations


def scan_python_tree(root):
    violations = []
    for path in sorted(root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        violations.extend(scan_python_source(path, source))
    return violations


class GuardScannerSelfTests(unittest.TestCase):
    def assertSnippetViolates(self, source):
        violations = scan_python_source(Path("snippet.py"), source)
        self.assertNotEqual(violations, [])

    def assertSnippetPasses(self, source):
        violations = scan_python_source(Path("snippet.py"), source)
        self.assertEqual(violations, [])

    def test_fails_on_import_subprocess(self):
        self.assertSnippetViolates("import subprocess\n")

    def test_fails_on_from_urllib_import(self):
        self.assertSnippetViolates("from urllib import request\n")

    def test_fails_on_os_system_call(self):
        self.assertSnippetViolates('import os\nos.system("x")\n')

    def test_fails_on_git_push_string_literal(self):
        self.assertSnippetViolates('command = "git push origin main"\n')

    def test_passes_on_docstring_and_comment_mentioning_github(self):
        self.assertSnippetPasses('"""GitHub is mentioned in documentation."""\n# GitHub\n')

    def test_current_src_tree_has_no_forbidden_automation(self):
        self.assertEqual(scan_python_tree(SRC), [])


class NoAutomationTests(unittest.TestCase):
    def test_src_has_no_forbidden_automation(self):
        self.assertEqual(scan_python_tree(SRC), [])


if __name__ == "__main__":
    unittest.main()
