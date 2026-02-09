from .config import ProjectConfig, load_config, OutputConfig
from .discovery import discover_files, load_gitignore_spec
from .renderers import human, llm, markdown
from typing import List, Tuple, Optional
import os
import sys
import subprocess
import platform
import datetime
import pathspec  # <-- MODIFICATION: Import pathspec
from pathspec.patterns import GitWildMatchPattern # <-- MODIFICATION

class ProjectEngine:
    """
    Core engine for VibeCode projects.
    Handles file gathering, filtering, and rendering pipelines.
    """
    
    def __init__(self, config_path: str):
        self.config_path = os.path.abspath(config_path)
        self.project_root = os.path.dirname(self.config_path)
        self.config: ProjectConfig = load_config(self.config_path)
        self.gitignore_spec = load_gitignore_spec(self.project_root)
        
        # --- MODIFICATION: Compile a second spec for the 'exclude' list ---
        self.exclude_spec = pathspec.PathSpec.from_lines(
            GitWildMatchPattern, self.config.exclude
        )
        # --- END MODIFICATION ---

    def gather_files(self) -> List[Tuple[str, str]]:
        """
        Gathers, filters, and sorts all files.
        Returns a list of (relative_path, content) tuples.
        """
        
        # 1. Start with the explicit 'files' list
        # These are relative to the config file (project root)
        explicit_files = [
            os.path.join(self.project_root, f) for f in self.config.files
        ]
        
        # 2. Add autodiscovered files
        discovered_files = []
        # --- MODIFICATION: Check for autodiscover_py OR autodiscover_ext ---
        if self.config.autodiscover_py or self.config.autodiscover_ext:
            all_files = discover_files(self.project_root, self.gitignore_spec)
            
            # Build the list of extensions to check
            extensions_to_check = list(self.config.autodiscover_ext)
            if self.config.autodiscover_py:
                extensions_to_check.append('.py')
            
            extensions = tuple(extensions_to_check)
            # --- END MODIFICATION ---

            for f in all_files:
                if f.endswith(extensions):
                    discovered_files.append(f)
                    
        # 3. Combine and de-duplicate (preserving order)
        final_file_list = []
        seen = set()
        for f in explicit_files + discovered_files:
            f = os.path.normpath(f)
            if f not in seen and os.path.isfile(f):
                # --- MODIFICATION: Use pathspec for exclude logic ---
                rel_path = os.path.relpath(f, self.project_root)
                rel_path_posix = rel_path.replace(os.path.sep, '/')
                
                # Check if the file is NOT matched by the 'exclude' spec
                if not self.exclude_spec.match_file(rel_path_posix):
                    seen.add(f)
                    final_file_list.append(f)
                # --- END MODIFICATION ---

        # 4. Read content
        file_contents = []
        for path in final_file_list:
            rel_path = os.path.relpath(path, self.project_root).replace(os.path.sep, '/')
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                file_contents.append((rel_path, content))
            except Exception:
                # Fail gracefully on unreadable files
                file_contents.append((rel_path, f"Error: Could not read file"))
                
        return file_contents

    def _capture_runtime_environment(self) -> str:
        """
        Generates the content for the synthetic 'vibe_snapshot_env.txt'.
        Captures Python version, OS, and pip dependencies.
        
        ECR #008: Frozen State Runtime Context Injection
        """
        # 1. Header Metadata (Critical context for the LLM/User)
        header = [
            "# VIBECODE SNAPSHOT ENVIRONMENT",
            f"# Generated: {datetime.datetime.now().isoformat()}",
            f"# Platform: {platform.system()} {platform.release()}",
            f"# Python Version: {sys.version.split()[0]}",
            f"# Executable: {sys.executable}",
            "-" * 40,
            ""
        ]

        # 2. Dependency Capture (The "pip freeze")
        dependencies = ""
        try:
            # Use sys.executable to ensure we use the CURRENT environment's pip
            result = subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                capture_output=True,
                text=True,
                timeout=10  # Hard constraint: Don't hang the GUI > 10s
            )
            if result.returncode == 0:
                dependencies = result.stdout
            else:
                dependencies = f"# Error capturing dependencies: {result.stderr}"
        except subprocess.TimeoutExpired:
            dependencies = "# Error: pip freeze timed out after 10 seconds"
        except Exception as e:
            dependencies = f"# Failed to run pip freeze: {str(e)}"

        return "\n".join(header) + dependencies

    def render(self, pipeline_type: str, output_path_override: Optional[str], 
               file_data_override: Optional[List[Tuple[str, str]]] = None):
        """
        Gathers files and directs them to the correct render pipeline.
        
        Args:
            pipeline_type: 'human', 'llm', or 'markdown'
            output_path_override: Optional path override for output
            file_data_override: Optional pre-processed file data (e.g., with redactions applied)
        """
        file_data = file_data_override if file_data_override else self.gather_files()
        
        # ECR #008: Inject synthetic runtime environment file
        env_content = self._capture_runtime_environment()
        file_data.append(("vibe_snapshot_env.txt", env_content))
        
        if pipeline_type == 'human':
            output_path = output_path_override or self.config.output.human_pdf
            renderer = human.HumanRenderer(
                style=self.config.output.pygments_style
            )
            renderer.render(file_data, output_path)

        elif pipeline_type == 'llm':
            output_path = output_path_override or self.config.output.llm_pdf
            renderer = llm.LLMRenderer()
            renderer.render(file_data, output_path)
            
        elif pipeline_type == 'markdown':
            # Default to appending .md if no override
            output_path = output_path_override or self.config.output.llm_pdf.replace('.pdf', '.md')
            renderer = markdown.MarkdownRenderer()
            renderer.render(file_data, output_path)