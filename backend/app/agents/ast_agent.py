import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel
from tree_sitter_languages import get_parser

class ImportData(BaseModel):
    module: str
    names: List[str]
    raw: str

class FunctionData(BaseModel):
    name: str
    start_line: int
    end_line: int
    decorators: List[str]
    parameters: List[str]
    complexity: int
    loc: int

class ClassData(BaseModel):
    name: str
    start_line: int
    end_line: int
    decorators: List[str]
    methods: List[FunctionData]
    bases: List[str]
    complexity: int
    loc: int

class ModuleData(BaseModel):
    file_path: str
    docstring: Optional[str]
    imports: List[ImportData]
    classes: List[ClassData]
    functions: List[FunctionData]

class AstAgent:
    def __init__(self):
        # Obtain python parser
        self.parser = get_parser("python")

    def _get_node_text(self, node, source: bytes) -> str:
        return source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

    def _calculate_complexity(self, node) -> int:
        """
        Calculate AST-based cyclomatic complexity by counting control-flow decision points.
        Decision points: if, for, while, except, and, or, conditional_expression
        """
        complexity = 1
        decision_types = {
            "if_statement",
            "for_statement",
            "while_statement",
            "except_clause",
            "conditional_expression"
        }
        
        # Helper to traverse subtree
        def traverse(n):
            nonlocal complexity
            if n.type in decision_types:
                complexity += 1
            elif n.type in ("boolean_operator", "binary_operator"):
                # Count and/or inside expressions
                op_text = n.child_by_field_name("operator")
                if op_text and op_text.type in ("and", "or"):
                    complexity += 1
            
            for child in n.children:
                traverse(child)

        traverse(node)
        return complexity

    def _extract_decorators(self, node, source: bytes) -> List[str]:
        decorators = []
        # In tree-sitter, decorator nodes are often siblings preceding the definition
        # or children of a decorated_definition wrapper.
        # If the parent is decorated_definition, let's find all decorator children.
        parent = node.parent
        if parent and parent.type == "decorated_definition":
            for child in parent.children:
                if child.type == "decorator":
                    dec_text = self._get_node_text(child, source).strip()
                    # Clean decorator name (e.g. @router.get("/") -> router.get)
                    match = dec_text.split("(")[0].replace("@", "")
                    decorators.append(match)
        return decorators

    def _extract_parameters(self, node, source: bytes) -> List[str]:
        parameters = []
        params_node = node.child_by_field_name("parameters")
        if params_node:
            for child in params_node.children:
                # parameters child nodes could be identifier, typed_parameter, default_parameter, etc.
                if child.type in ("identifier", "typed_parameter", "default_parameter", "dictionary_splat_pattern", "list_splat_pattern"):
                    param_text = self._get_node_text(child, source).split(":")[0].split("=")[0].strip()
                    if param_text and param_text not in ("(", ")", ",", "*", "**"):
                        parameters.append(param_text)
        return parameters

    def _extract_docstring(self, body_node, source: bytes) -> Optional[str]:
        if not body_node or len(body_node.children) == 0:
            return None
        first_child = body_node.children[0]
        # In python, standard docstrings are expressions containing string literals
        if first_child.type == "expression_statement":
            expr_child = first_child.children[0]
            if expr_child.type == "string":
                text = self._get_node_text(expr_child, source)
                # Strip triple quotes
                return text.strip('"""').strip("'''").strip()
        return None

    def _parse_imports(self, root_node, source: bytes) -> List[ImportData]:
        imports = []

        def traverse(node):
            if node.type == "import_statement":
                # E.g. import os, sys
                raw_text = self._get_node_text(node, source)
                names = []
                for child in node.children:
                    if child.type in ("dotted_name", "aliased_name"):
                        names.append(self._get_node_text(child, source))
                imports.append(ImportData(module="", names=names, raw=raw_text))

            elif node.type == "import_from_statement":
                # E.g. from os import path
                raw_text = self._get_node_text(node, source)
                module_node = node.child_by_field_name("module_name") or node.child_by_field_name("module")
                module_name = self._get_node_text(module_node, source) if module_node else ""
                
                names = []
                # In from imports, names are in wildcard or dotted/aliased format
                for child in node.children:
                    if child.type == "wildcard_import":
                        names.append("*")
                    elif child.type in ("dotted_name", "aliased_name", "identifier"):
                        names.append(self._get_node_text(child, source))
                
                # Filter out the module token if it is also listed as a child name
                names = [n for n in names if n != module_name and n not in ("from", "import")]
                imports.append(ImportData(module=module_name, names=names, raw=raw_text))
            
            for child in node.children:
                traverse(child)

        traverse(root_node)
        return imports

    def _extract_classes_and_functions(self, root_node, source: bytes) -> Tuple[List[ClassData], List[FunctionData]]:
        classes = []
        functions = []

        def visit(node):
            # Visit children of decorated_definition if we hit one
            if node.type == "decorated_definition":
                for child in node.children:
                    if child.type in ("class_definition", "function_definition"):
                        visit(child)
                return

            if node.type == "class_definition":
                class_name_node = node.child_by_field_name("name")
                class_name = self._get_node_text(class_name_node, source) if class_name_node else "UnknownClass"
                
                # Base classes
                bases = []
                superclasses = node.child_by_field_name("superclasses")
                if superclasses:
                    for arg in superclasses.children:
                        if arg.type in ("identifier", "attribute"):
                            bases.append(self._get_node_text(arg, source))
                
                # Class body
                body_node = node.child_by_field_name("body")
                methods = []
                
                if body_node:
                    for child in body_node.children:
                        # Extract methods
                        # It might be a decorated method
                        method_node = child
                        if child.type == "decorated_definition":
                            for sub in child.children:
                                if sub.type == "function_definition":
                                    method_node = sub
                        
                        if method_node.type == "function_definition":
                            method_name_node = method_node.child_by_field_name("name")
                            method_name = self._get_node_text(method_name_node, source) if method_name_node else "unknown_method"
                            
                            start_l = method_node.start_point[0] + 1
                            end_l = method_node.end_point[0] + 1
                            loc = end_l - start_l + 1
                            
                            methods.append(FunctionData(
                                name=method_name,
                                start_line=start_l,
                                end_line=end_l,
                                decorators=self._extract_decorators(method_node, source),
                                parameters=self._extract_parameters(method_node, source),
                                complexity=self._calculate_complexity(method_node),
                                loc=loc
                            ))

                start_l = node.start_point[0] + 1
                end_l = node.end_point[0] + 1
                loc = end_l - start_l + 1
                
                # Class complexity is the sum of its methods plus 1
                class_complexity = 1 + sum(m.complexity for m in methods)

                classes.append(ClassData(
                    name=class_name,
                    start_line=start_l,
                    end_line=end_l,
                    decorators=self._extract_decorators(node, source),
                    methods=methods,
                    bases=bases,
                    complexity=class_complexity,
                    loc=loc
                ))
                return # Don't traverse deeper into class children here (handled via methods)

            elif node.type == "function_definition":
                func_name_node = node.child_by_field_name("name")
                func_name = self._get_node_text(func_name_node, source) if func_name_node else "unknown_function"
                
                start_l = node.start_point[0] + 1
                end_l = node.end_point[0] + 1
                loc = end_l - start_l + 1

                functions.append(FunctionData(
                    name=func_name,
                    start_line=start_l,
                    end_line=end_l,
                    decorators=self._extract_decorators(node, source),
                    parameters=self._extract_parameters(node, source),
                    complexity=self._calculate_complexity(node),
                    loc=loc
                ))
                return

            for child in node.children:
                visit(child)

        visit(root_node)
        return classes, functions

    def parse_file(self, file_path: Path, relative_path: str) -> ModuleData:
        """Parse a single python file and extract module-level AST structure."""
        with open(file_path, "rb") as f:
            source = f.read()

        tree = self.parser.parse(source)
        root_node = tree.root_node

        imports = self._parse_imports(root_node, source)
        classes, functions = self._extract_classes_and_functions(root_node, source)
        
        # Read module docstring from root body
        docstring = self._extract_docstring(root_node, source)

        return ModuleData(
            file_path=relative_path,
            docstring=docstring,
            imports=imports,
            classes=classes,
            functions=functions
        )

    def run(self, checkout_path: Path, python_files: List[str]) -> Dict[str, Any]:
        """
        Parses all Python files and compiles AST data.
        Returns a dict containing 'modules' mapping and list of 'symbols'.
        """
        modules = {}
        symbols = []

        for rel_path in python_files:
            full_path = checkout_path / rel_path
            if full_path.exists() and full_path.is_file():
                try:
                    module_data = self.parse_file(full_path, rel_path)
                    modules[rel_path] = module_data.model_dump()
                    
                    # Gather symbols
                    # Classes
                    for cls in module_data.classes:
                        symbols.append({
                            "kind": "class",
                            "name": cls.name,
                            "qualified_name": f"{rel_path.replace('.py', '').replace('/', '.')}.{cls.name}",
                            "file_path": rel_path,
                            "start_line": cls.start_line,
                            "end_line": cls.end_line,
                            "decorators": cls.decorators,
                            "complexity": cls.complexity
                        })
                        # Methods
                        for m in cls.methods:
                            symbols.append({
                                "kind": "method",
                                "name": m.name,
                                "qualified_name": f"{rel_path.replace('.py', '').replace('/', '.')}.{cls.name}.{m.name}",
                                "file_path": rel_path,
                                "start_line": m.start_line,
                                "end_line": m.end_line,
                                "decorators": m.decorators,
                                "complexity": m.complexity
                            })
                    # Top level functions
                    for f in module_data.functions:
                        symbols.append({
                            "kind": "function",
                            "name": f.name,
                            "qualified_name": f"{rel_path.replace('.py', '').replace('/', '.')}.{f.name}",
                            "file_path": rel_path,
                            "start_line": f.start_line,
                            "end_line": f.end_line,
                            "decorators": f.decorators,
                            "complexity": f.complexity
                        })
                except Exception as e:
                    # Log exception or record error but don't crash the whole run
                    print(f"Error parsing file {rel_path}: {e}")

        return {
            "modules": modules,
            "symbols": symbols
        }
