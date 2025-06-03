import os

import subprocess
from tree_sitter import Language, Parser, Node
import tree_sitter_rescript
import json
from collections import defaultdict
from rescript_ast_diff.differ import RescriptFileDiff


def extract_module_name(filepath):
    return os.path.basename(filepath).replace('.res', '').title().replace('_', '').replace('-', '')

def clone_repo(repo_url, local_path):
    if not os.path.exists(local_path):
        print(f'Cloning repository to {local_path}...')
        subprocess.run(['git', 'clone', repo_url, local_path], check=True)
    else:
        print(f'Repository already exists at {local_path}')

def get_changed_files(branch_or_commit, new_commit, local_path):
    old_cwd = os.getcwd()
    os.chdir(local_path)

    try:
        subprocess.run(['git', 'checkout', '-f', branch_or_commit], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        commit = subprocess.run(['git', 'rev-parse', branch_or_commit], check=True, stdout=subprocess.PIPE).stdout.decode().strip()
        diff = subprocess.run(['git', 'diff', '--name-only', commit, new_commit], check=True, stdout=subprocess.PIPE).stdout.decode()

        files = [file for file in diff.split('\n') if file.strip() and file.endswith('.res')]

        return files
    finally:
        os.chdir(old_cwd)

def compare_commits(repo_url, local_repo_path, branch_or_commit, current_commit, output_dir):
    try:
        RS_LANGUAGE = Language(tree_sitter_rescript.language())
        parser = Parser(RS_LANGUAGE)
        clone_repo(repo_url, local_repo_path)

        print('Getting changed files...')
        changed_files = get_changed_files(branch_or_commit, current_commit, local_repo_path)
        print(f'Found {len(changed_files)} changed ReScript files')

        file_node_dict = defaultdict(list)

        file_paths = [os.path.join(local_repo_path, file) for file in changed_files]

        print('Processing modules for previous commit...')
        for changed_file in file_paths:
            if os.path.exists(changed_file):
                module_name = extract_module_name(changed_file)
                ast = parser.parse(open(changed_file, "rb").read())
                file_node_dict[module_name].append(ast)

        print('Switching to current commit...')
        old_cwd = os.getcwd()
        os.chdir(local_repo_path)
        subprocess.run(['git', 'checkout', '-f', current_commit], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.chdir(old_cwd)

        print('Processing modules for current commit...')
        for changed_file in file_paths:
            if os.path.exists(changed_file):
                module_name = extract_module_name(changed_file)
                ast = parser.parse(open(changed_file, "rb").read())
                file_node_dict[module_name].append(ast)

        print('Generating changes...')

        os.makedirs(output_dir, exist_ok=True)
        all_changes = []
        for module_name, asts_list in file_node_dict.items():
            if len(asts_list) == 2:
                old_node, new_node = asts_list
                diff = RescriptFileDiff(old_node, new_node, module_name)
                changes = diff.process_files()
                all_changes.append(changes.to_dict())

        final_output_path = os.path.join(output_dir, "detailed_changes.json")
        with open(final_output_path, "w") as f:
            json.dump(all_changes, f, indent = 3)
        
        print("Changes written to - ", final_output_path)

    except Exception as e:
        print("ERROR - ", e)
        pass