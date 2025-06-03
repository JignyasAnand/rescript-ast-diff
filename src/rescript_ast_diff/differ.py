import subprocess
import json
import re
from collections import defaultdict
from tree_sitter import Language, Parser, Node
import tree_sitter_rescript
import hashlib
import os


class DetailedChanges:
    def __init__(self, module_name):
        self.moduleName = module_name
        self.addedFunctions = []
        self.modifiedFunctions = []
        self.deletedFunctions = []
        self.addedTypes = []
        self.modifiedTypes = []
        self.deletedTypes = []
        self.addedExternals = []
        self.modifiedExternals = []
        self.deletedExternals = []

    def to_dict(self):
        return {
            "moduleName": self.moduleName,
            "addedFunctions": self.addedFunctions,
            "modifiedFunctions": self.modifiedFunctions,
            "deletedFunctions": self.deletedFunctions,
            "addedTypes": self.addedTypes,
            "modifiedTypes": self.modifiedTypes,
            "deletedTypes": self.deletedTypes,
            "addedExternals": self.addedExternals,
            "modifiedExternals": self.modifiedExternals,
            "deletedExternals": self.deletedExternals,
        }

    def __str__(self):
        return (
            f"Module: {self.moduleName}\n"
            f"Added Functions: {self.addedFunctions}\n"
            f"Modified Functions: {self.modifiedFunctions}\n"
            f"Deleted Functions: {self.deletedFunctions}\n"
            f"Added Types: {self.addedTypes}\n"
            f"Modified Types: {self.modifiedTypes}\n"
            f"Deleted Types: {self.deletedTypes}\n"
            f"Added Externals: {self.addedExternals}\n"
            f"Modified Externals: {self.modifiedExternals}\n"
            f"Deleted Externals: {self.deletedExternals}"
        )


def format_rescript_file(file_pth):
    try:
        subprocess.run(["npx", "rescript", "format", file_pth], capture_output=True)
    except:
        pass


class RescriptFileDiff:
    def __init__(self, old_file_ast, new_file_ast, module_name=""):
        self.old_file_root = old_file_ast.root_node
        self.new_file_root = new_file_ast.root_node

        self.module_name = module_name
    
    def get_decl_name(self, node: Node, node_type: str, name_type: str) -> str:
        for child in node.children:
            if node_type and child.type == node_type:
                for grandchild in child.children:
                    if grandchild.is_named and grandchild.type == name_type:
                        return grandchild.text.decode(errors="ignore")
            elif not node_type and child.is_named and child.type == name_type:
                return child.text.decode(errors="ignore")
        return None

    def ast_to_tuple(self, node: Node) -> tuple:
        named_children = [c for c in node.children if c.is_named]
        if not named_children:
            text = node.text.decode(errors="ignore")
            return (node.type, text)
        return (
            node.type,
            tuple(self.ast_to_tuple(c) for c in named_children)
        )

    def extract_components(self, root: Node) -> tuple:
        stack = [root]
        functions = {}
        types = {}
        externals = {}

        while stack:
            node = stack.pop()

            if node.type == "let_declaration":
                name = self.get_decl_name(node, "let_binding", "value_identifier")
                if name:
                    ast_repr = self.ast_to_tuple(node)
                    body_text = node.text.decode(errors="ignore")
                    functions[name] = (ast_repr, body_text)

            elif node.type == "type_declaration":
                name = self.get_decl_name(node, "type_binding", "type_identifier")
                if name:
                    ast_repr = self.ast_to_tuple(node)
                    body_text = node.text.decode(errors="ignore")
                    types[name] = (ast_repr, body_text)

            elif node.type == "external_declaration":
                name = self.get_decl_name(node, None, "value_identifier")
                if name:
                    ast_repr = self.ast_to_tuple(node)
                    body_text = node.text.decode(errors="ignore")
                    externals[name] = (ast_repr, body_text)

            else:
                for child in reversed(node.children):
                    if child.is_named:
                        stack.append(child)

        return functions, types, externals

    def diff_components(self, before_map: dict, after_map: dict) -> dict:
        before_names = set(before_map.keys())
        after_names = set(after_map.keys())

        added_names = after_names - before_names
        deleted_names = before_names - after_names
        common = before_names & after_names

        added = [(n, after_map[n][1]) for n in sorted(added_names)]
        deleted = [(n, before_map[n][1]) for n in sorted(deleted_names)]

        modified = []
        for name in sorted(common):
            old_ast, old_body = before_map[name]
            new_ast, new_body = after_map[name]
            if old_ast != new_ast:
                modified.append((name, old_body, new_body))

        return {"added": added, "deleted": deleted, "modified": modified}

    def process_files(self) -> DetailedChanges:
        old_funcs, old_types, old_ext = self.extract_components(self.old_file_root)
        new_funcs, new_types, new_ext = self.extract_components(self.new_file_root)

        changes = DetailedChanges(self.module_name)

        funcs_diff = self.diff_components(old_funcs, new_funcs)
        changes.addedFunctions = funcs_diff["added"]
        changes.deletedFunctions = funcs_diff["deleted"]
        changes.modifiedFunctions = funcs_diff["modified"]

        types_diff = self.diff_components(old_types, new_types)
        changes.addedTypes = types_diff["added"]
        changes.deletedTypes = types_diff["deleted"]
        changes.modifiedTypes = types_diff["modified"]

        ext_diff = self.diff_components(old_ext, new_ext)
        changes.addedExternals = ext_diff["added"]
        changes.deletedExternals = ext_diff["deleted"]
        changes.modifiedExternals = ext_diff["modified"]

        return changes
