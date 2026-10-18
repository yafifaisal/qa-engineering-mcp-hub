"""Language-aware parsing that never executes repository content.

Purpose: extract symbols and source references for supported languages.
Milestone: 05
Status: IMPLEMENTED
Ownership: knowledge.code_parser
Dependencies: The Python standard-library parser and knowledge evidence labels.
Expected tests: supported syntax, malformed files, and unsupported languages.
"""

import ast
import re
from dataclasses import dataclass

from qa_mcp_hub.core.enums import EpistemicStatus

_HTTP = {"get", "post", "put", "delete", "patch", "route", "api_route"}
_PUBLISH = {"publish", "produce", "send"}
_CONSUME = {"subscribe", "consume", "poll"}
_JOBS = {"schedule", "cron", "apply_async"}
_DATABASE = {"execute", "executemany"}
_GO_FUNC = re.compile(r"^func(?:\s+\([^)]*\))?\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
_IMPORT_LITERAL = re.compile(r"""["']([^"']+)["']""")
_JAVA_TYPE = re.compile(
    r"^\s*(?:public|private|protected)?\s*(?:class|interface|enum)\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)",
    re.M,
)
_JAVA_METHOD = re.compile(
    r"^\s*(?:public|private|protected)\s+(?:static\s+)?[\w.<>,\[\]]+\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.M,
)
_JAVA_IMPORT = re.compile(r"^\s*import\s+([\w.]+)\s*;", re.M)
_JS_FUNC = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)",
    re.M,
)
_JS_CLASS = re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)", re.M)
_PATTERN_REASON = "pattern parser is not a full language parser"


@dataclass(frozen=True)
class ParsedSymbol:
    """One name found in source, with the parser's evidence label."""

    name: str
    kind: str
    start_line: int
    end_line: int
    evidence: EpistemicStatus
    detail: str = ""


@dataclass(frozen=True)
class ParsedReference:
    """One source reference. It does not claim the target runs."""

    kind: str
    source_name: str
    target_name: str
    target_hint: str | None
    start_line: int
    evidence: EpistemicStatus
    detail: str


@dataclass(frozen=True)
class ParseResult:
    """Parser output for one file. Unsupported files stay UNKNOWN."""

    language: str
    parser: str
    symbols: tuple[ParsedSymbol, ...]
    references: tuple[ParsedReference, ...]
    evidence: EpistemicStatus
    reason: str


def language_for(path: str) -> str:
    """Return the supported language id, or unknown."""
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "py": "python",
        "go": "go",
        "java": "java",
        "js": "javascript",
        "jsx": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
    }.get(suffix, "unknown")


def parse_source(path: str, text: str) -> ParseResult:
    """Parse one file. A syntax failure is UNKNOWN and does not raise."""
    language = language_for(path)
    if language == "python":
        return _parse_python(text)
    if language == "go":
        return _parse_patterns(language, text, _GO_FUNC, None)
    if language == "java":
        return _parse_java(text)
    if language in {"javascript", "typescript"}:
        return _parse_script(language, text)
    return ParseResult(
        language="unknown",
        parser="none",
        symbols=(),
        references=(),
        evidence=EpistemicStatus.unknown,
        reason="no supported parser for this file",
    )


def module_hint(module: str) -> str | None:
    """Turn a dotted module into a relative Python path hint."""
    if not module or module.startswith("."):
        return None
    parts = [part for part in module.split(".") if part.isidentifier()]
    if not parts:
        return None
    return "/".join(parts) + ".py"


def _parse_python(text: str) -> ParseResult:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ParseResult(
            language="python",
            parser="ast",
            symbols=(),
            references=(),
            evidence=EpistemicStatus.unknown,
            reason="python syntax error",
        )
    visitor = _PythonVisitor()
    visitor.visit(tree)
    return ParseResult(
        language="python",
        parser="ast",
        symbols=tuple(visitor.symbols),
        references=tuple(visitor.references),
        evidence=EpistemicStatus.verified,
        reason="python ast parser",
    )


class _PythonVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.symbols: list[ParsedSymbol] = []
        self.references: list[ParsedReference] = []
        self._stack: list[str] = ["<module>"]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add_symbol(node.name, "class", node)
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._function(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._import(alias.name, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        if node.level == 0 and module:
            self._import(module, node.lineno)
        else:
            self.references.append(
                ParsedReference(
                    kind="import",
                    source_name=self._stack[-1],
                    target_name=module or ".",
                    target_hint=None,
                    start_line=node.lineno,
                    evidence=EpistemicStatus.unknown,
                    detail="relative import was not resolved",
                )
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        called = _call_parts(node.func)
        if called is not None:
            simple, attr = called
            self._classify_call(simple, attr, node.lineno)
        self.generic_visit(node)

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._add_symbol(node.name, "function", node)
        for decorator in node.decorator_list:
            route = _route_path(decorator)
            if route is None:
                continue
            self.symbols.append(
                ParsedSymbol(
                    name=node.name,
                    kind="route",
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    evidence=EpistemicStatus.verified,
                    detail=route or "/",
                )
            )
            self.references.append(
                ParsedReference(
                    kind="route",
                    source_name=node.name,
                    target_name=route or "/",
                    target_hint=None,
                    start_line=node.lineno,
                    evidence=EpistemicStatus.verified,
                    detail="route decorator appears in source; runtime registration "
                    "was not observed",
                )
            )
        self._stack.append(node.name)
        self.generic_visit(node)
        self._stack.pop()

    def _add_symbol(self, name: str, kind: str, node: ast.AST) -> None:
        end = getattr(node, "end_lineno", None)
        start = getattr(node, "lineno", 1)
        self.symbols.append(
            ParsedSymbol(
                name=name,
                kind=kind,
                start_line=start if isinstance(start, int) else 1,
                end_line=end if isinstance(end, int) else start,
                evidence=EpistemicStatus.verified,
            )
        )

    def _import(self, module: str, line: int) -> None:
        self.references.append(
            ParsedReference(
                kind="import",
                source_name=self._stack[-1],
                target_name=module,
                target_hint=module_hint(module),
                start_line=line,
                evidence=EpistemicStatus.unknown,
                detail="import target is not resolved yet",
            )
        )

    def _classify_call(self, simple: str, attr: str, line: int) -> None:
        label = attr or simple
        kind = ""
        if attr in _PUBLISH or simple in _PUBLISH:
            kind = "publisher"
        elif attr in _CONSUME or simple in _CONSUME:
            kind = "consumer"
        elif attr in _JOBS or simple in _JOBS:
            kind = "job"
        elif attr in _DATABASE or simple in _DATABASE:
            kind = "database"
        elif simple and not attr:
            kind = "call"
        if not kind:
            return
        evidence = (
            EpistemicStatus.verified if kind == "call" else EpistemicStatus.inferred
        )
        detail = (
            "call appears in source; runtime execution was not observed"
            if kind == "call"
            else "call name matches a supported pattern; runtime behavior was not "
            "observed"
        )
        self.references.append(
            ParsedReference(
                kind=kind,
                source_name=self._stack[-1],
                target_name=label,
                target_hint=None,
                start_line=line,
                evidence=evidence,
                detail=detail,
            )
        )


def _call_parts(func: ast.expr) -> tuple[str, str] | None:
    if isinstance(func, ast.Name):
        return func.id, ""
    if isinstance(func, ast.Attribute):
        owner = func.value.id if isinstance(func.value, ast.Name) else ""
        return owner, func.attr
    return None


def _route_path(decorator: ast.expr) -> str | None:
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not isinstance(func, ast.Attribute) or func.attr not in _HTTP:
        return None
    if not decorator.args:
        return ""
    first = decorator.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value[:200]
    return ""


def _parse_java(text: str) -> ParseResult:
    symbols = [
        ParsedSymbol(
            match.group(1),
            "class",
            _line_of(text, match.start()),
            _line_of(text, match.start()),
            EpistemicStatus.inferred,
        )
        for match in _JAVA_TYPE.finditer(text)
    ]
    symbols.extend(
        ParsedSymbol(
            match.group(1),
            "function",
            _line_of(text, match.start()),
            _line_of(text, match.start()),
            EpistemicStatus.inferred,
        )
        for match in _JAVA_METHOD.finditer(text)
    )
    references = [
        ParsedReference(
            "import",
            "<module>",
            match.group(1),
            module_hint(match.group(1)),
            _line_of(text, match.start()),
            EpistemicStatus.inferred,
            _PATTERN_REASON,
        )
        for match in _JAVA_IMPORT.finditer(text)
    ]
    return ParseResult(
        "java",
        "pattern",
        tuple(symbols),
        tuple(references),
        EpistemicStatus.inferred,
        _PATTERN_REASON,
    )


def _parse_script(language: str, text: str) -> ParseResult:
    symbols = [
        ParsedSymbol(
            match.group(1),
            "function",
            _line_of(text, match.start()),
            _line_of(text, match.start()),
            EpistemicStatus.inferred,
        )
        for match in _JS_FUNC.finditer(text)
    ]
    symbols.extend(
        ParsedSymbol(
            match.group(1),
            "class",
            _line_of(text, match.start()),
            _line_of(text, match.start()),
            EpistemicStatus.inferred,
        )
        for match in _JS_CLASS.finditer(text)
    )
    references = [
        ParsedReference(
            "import",
            "<module>",
            match.group(1),
            None,
            _line_of(text, match.start()),
            EpistemicStatus.inferred,
            _PATTERN_REASON,
        )
        for match in _IMPORT_LITERAL.finditer(text)
        if "import" in text[max(0, match.start() - 20) : match.start()]
        or "from" in text[max(0, match.start() - 20) : match.start()]
    ]
    return ParseResult(
        language,
        "pattern",
        tuple(symbols),
        tuple(references),
        EpistemicStatus.inferred,
        _PATTERN_REASON,
    )


def _parse_patterns(
    language: str,
    text: str,
    functions: re.Pattern[str],
    classes: re.Pattern[str] | None,
) -> ParseResult:
    symbols = [
        ParsedSymbol(
            match.group(1),
            "function",
            _line_of(text, match.start()),
            _line_of(text, match.start()),
            EpistemicStatus.inferred,
        )
        for match in functions.finditer(text)
    ]
    if classes is not None:
        symbols.extend(
            ParsedSymbol(
                match.group(1),
                "class",
                _line_of(text, match.start()),
                _line_of(text, match.start()),
                EpistemicStatus.inferred,
            )
            for match in classes.finditer(text)
        )
    return ParseResult(
        language,
        "pattern",
        tuple(symbols),
        (),
        EpistemicStatus.inferred,
        _PATTERN_REASON,
    )


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1
