import os
import re
import subprocess
import logging

logger = logging.getLogger()
config_file_extensions = ['json', 'yml', 'yaml', 'xml', 'properties', 'py', 'rb', 'php', 'toml', 'txt', 'kts']
config_file_patterns = [
    r'package', r'.*\.env', r'requirements', r'settings', r'pom',
    r'application', r'appsettings', r'web', r'Gemfile', r'config',
    r'go', r'Cargo', r'build', r'Dockerfile', r'docker-compose'
]


class Git:
    @staticmethod
    def get_repo_name(directory: str):
        try:
            url = subprocess.check_output(['git', 'remote', 'get-url', 'origin'], cwd=directory, text=True).strip()

            repo_name = os.path.splitext(os.path.basename(url))[0]
            return repo_name
        except Exception as e:
            raise Exception(f"Failed getting git repo name from directory: {directory}") from e

    @staticmethod
    def get_app_config(directory: str):
        found_files = []
        for root, dirs, files in os.walk(directory):
            if 'test' in root.lower() or 'venv' in root.lower() or 'lib' in root.lower() or '.git' in root.lower():
                continue
            for file in files:
                base_name, ext = os.path.splitext(file)
                ext = ext.lstrip('.')  # Remove o ponto da extensão

                # 1. Verifica arquivos COM extensão
                if ext in config_file_extensions:
                    for pattern in config_file_patterns:
                        if re.match(pattern, base_name):
                            found_files.append((file, os.path.join(root, file)))
                            break
                # 2. Verifica arquivos SEM extensão (ex: Dockerfile, Gemfile, etc)
                elif ext == '':
                    for pattern in config_file_patterns:
                        if re.match(pattern, file):
                            found_files.append((file, os.path.join(root, file)))
                            break
        return found_files