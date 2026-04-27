


class TreeSitterAnalyserMaps:
    def get_parser(self, ext: str):
        from tree_sitter import Language, Parser
        import tree_sitter_python as tspython
        import tree_sitter_java as tsjava
        import tree_sitter_kotlin as tskotlin
        import tree_sitter_c_sharp as tscsharp
        import tree_sitter_javascript as tsjs
        import tree_sitter_typescript as tsts
        import tree_sitter_html as tshtml
        import tree_sitter_markdown as tsmd
        import tree_sitter_json as tsjson
        import tree_sitter_swift as tsswift
        import tree_sitter_go as tsgo
        import tree_sitter_rust as tsrust
        _map = {
            '.py':   Language(tspython.language()),
            '.java': Language(tsjava.language()),
            '.kt':   Language(tskotlin.language()),
            '.cs':   Language(tscsharp.language()),
            '.js':   Language(tsjs.language()),
            '.ts':   Language(tsts.language_typescript()),
            '.tsx':  Language(tsts.language_tsx()),
            '.html': Language(tshtml.language()),
            '.md':   Language(tsmd.language()),
            '.json': Language(tsjson.language()),
            '.swift':Language(tsswift.language()),
            '.go':   Language(tsgo.language()),
            '.rs':   Language(tsrust.language()),
        }
        return _map.get(ext)

    def get_analyser(self, ext: str):
        from commons.ts_analyzers.csharp_analyzer import CSharpAnalyzer
        from commons.ts_analyzers.go_analyzer import GoAnalyzer
        from commons.ts_analyzers.java_analyzer import JavaAnalyzer
        from commons.ts_analyzers.javascript_analyzer import JavaScriptAnalyzer
        from commons.ts_analyzers.kotlin_analyzer import KotlinAnalyzer
        from commons.ts_analyzers.noop_analyzer import NoopAnalyzer
        from commons.ts_analyzers.python_analyzer import PythonAnalyzer
        from commons.ts_analyzers.rust_analyzer import RustAnalyzer
        from commons.ts_analyzers.swift_analyzer import SwiftAnalyzer
        from commons.ts_analyzers.typescript_analyzer import TypeScriptAnalyzer
        _map = {
            '.java': JavaAnalyzer(),
            '.py': PythonAnalyzer(),
            '.js': JavaScriptAnalyzer(),
            '.ts': TypeScriptAnalyzer(),
            '.tsx': TypeScriptAnalyzer(),
            '.cs': CSharpAnalyzer(),
            '.kt': KotlinAnalyzer(),
            '.go': GoAnalyzer(),
            '.swift': SwiftAnalyzer(),
            '.rs': RustAnalyzer(),
            '.html': NoopAnalyzer(),
            '.md': NoopAnalyzer(),
            '.json': NoopAnalyzer()
        }
        return _map.get(ext, NoopAnalyzer())

    def get_language(self, ext: str):
        _map = {
            '.py': 'python',
            '.java': 'java',
            '.kt': 'kotlin',
            '.cs': 'c_sharp',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'tsx',
            '.html': 'html',
            '.md': 'markdown',
            '.json': 'json',
            '.swift': 'swift',
            '.go': 'go',
            '.rs': 'rust',
        }
        return _map.get(ext)