"""
Command-Line Interface for VibeCode.
"""
import typer
import os
import re
import json
import zlib
import base64
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

# Try importing pypdf, handle case if not installed
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

from .engine import ProjectEngine
from .gui import run_gui

app = typer.Typer(
    help="Vibecode: Codebase-to-PDF snapshot generator."
)

console = Console()


@app.command(name="human", help="Generate a human-readable, syntax-highlighted PDF.")
def run_human(
    ctx: typer.Context,
    config_path: str = typer.Option(
        ".vibecode.yaml", "--config", "-c",
        help="Path to the .vibecode.yaml config file."
    ),
    output_path: str = typer.Option(
        None, "--output", "-o",
        help="Output PDF file path. Overrides config."
    )
):
    """
    Generate a Human-Readable PDF with syntax highlighting.
    """
    console.print(
        Panel.fit(
            f"[bold blue]Generating HUMAN-readable PDF[/bold blue]\nConfig: {config_path}",
            border_style="blue"
        )
    )
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("Loading configuration...", total=None)
            engine = ProjectEngine(config_path)
            
            progress.update(task, description="Gathering files...")
            progress.update(task, description="Rendering PDF (this may take a moment)...")
            engine.render(pipeline_type='human', output_path_override=output_path)
        
        console.print("[bold green]✓[/bold green] Successfully generated Human-readable PDF!")
        
    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="llm", help="Generate a machine-readable, LLM-optimized text-only PDF.")
def run_llm(
    ctx: typer.Context,
    config_path: str = typer.Option(
        ".vibecode.yaml", "--config", "-c",
        help="Path to the .vibecode.yaml config file."
    ),
    output_path: str = typer.Option(
        None, "--output", "-o",
        help="Output PDF file path. Overrides config."
    )
):
    """
    Generate an LLM-optimized PDF for AI context injection.
    """
    console.print(
        Panel.fit(
            f"[bold magenta]Generating LLM-optimized PDF[/bold magenta]\nConfig: {config_path}",
            border_style="magenta"
        )
    )
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("Loading configuration...", total=None)
            engine = ProjectEngine(config_path)
            
            progress.update(task, description="Gathering files...")
            progress.update(task, description="Rendering PDF with secret scrubbing...")
            engine.render(pipeline_type='llm', output_path_override=output_path)
        
        console.print("[bold green]✓[/bold green] Successfully generated LLM PDF!")
        
    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="unpack", help="Restore a codebase from a Vibecode PDF snapshot.")
def run_unpack(
    pdf_path: str = typer.Argument(..., help="Path to the Vibecode PDF snapshot."),
    output_dir: str = typer.Option(
        ".", "--output", "-o",
        help="Directory to unpack files into (default: current directory)."
    ),
    force_scrape: bool = typer.Option(
        False, "--force-scrape",
        help="EMERGENCY ONLY: Attempt lossy text scraping if manifest is corrupt."
    )
):
    """
    Unpacks a Vibecode PDF back into a working codebase.
    
    Primary Method: Digital Twin Manifest (100% fidelity)
    Emergency: --force-scrape for lossy text extraction
    
    ECR #006: Silent fallback has been DISABLED to protect code integrity.
    """
    if PdfReader is None:
        console.print("[bold red]Error:[/bold red] 'pypdf' is not installed. Please run [bold]pip install pypdf[/bold]")
        raise typer.Exit(code=1)

    if not os.path.exists(pdf_path):
        console.print(f"[bold red]Error:[/bold red] File not found: {pdf_path}")
        raise typer.Exit(code=1)

    console.print(
        Panel.fit(
            f"[bold green]Unpacking Snapshot[/bold green]\nSource: {pdf_path}\nTarget: {os.path.abspath(output_dir)}",
            border_style="green"
        )
    )

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            
            task = progress.add_task("Reading PDF...", total=None)
            
            # 1. Read PDF
            try:
                reader = PdfReader(pdf_path)
                full_text = ""
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
            except Exception as e:
                console.print(f"[bold red]Error reading PDF:[/bold red] {e}")
                raise typer.Exit(code=1)

            # 2. Attempt Digital Twin Manifest Extraction (The Safe Path)
            progress.update(task, description="Searching for Digital Twin Manifest...")
            
            manifest_pattern = r"--- VIBECODE_RESTORE_BLOCK_START ---\s*(.*?)\s*--- VIBECODE_RESTORE_BLOCK_END ---"
            match = re.search(manifest_pattern, full_text, re.DOTALL)

            files_restored = 0
            manifest_error = None
            
            if match:
                progress.update(task, description="Manifest found! Restoring with high fidelity...")
                payload = match.group(1).strip()
                
                try:
                    # Decode & Decompress
                    compressed_data = base64.b64decode(payload)
                    json_bytes = zlib.decompress(compressed_data)
                    file_map = json.loads(json_bytes.decode('utf-8'))
                    
                    # Restore files
                    for rel_path, content in file_map.items():
                        # Security check
                        safe_path = os.path.normpath(rel_path)
                        if safe_path.startswith("..") or os.path.isabs(safe_path):
                            console.print(f"[yellow]Skipping unsafe path:[/yellow] {rel_path}")
                            continue

                        full_out_path = os.path.join(output_dir, safe_path)
                        os.makedirs(os.path.dirname(full_out_path), exist_ok=True)
                        
                        with open(full_out_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        files_restored += 1
                        
                    console.print(f"[bold green]✓[/bold green] Restored {files_restored} files via Digital Twin Manifest.")
                    return

                except Exception as e:
                    manifest_error = str(e)
            else:
                manifest_error = "No Digital Twin manifest found in PDF."

        # ECR #006: Integrity Check Failed - Abort or Break Glass
        console.print(f"\n[bold red]❌ CRITICAL:[/bold red] {manifest_error}")
        
        if force_scrape:
            # Emergency "Break Glass" Path
            console.print("")
            console.print("[bold yellow]" + "=" * 60 + "[/bold yellow]")
            console.print("[bold yellow]⚠️  WARNING: EMERGENCY VISUAL SCRAPE ACTIVE[/bold yellow]")
            console.print("[bold yellow]" + "=" * 60 + "[/bold yellow]")
            console.print("[yellow]You are bypassing Digital Twin integrity checks.[/yellow]")
            console.print("[yellow]Visual PDF scraping DESTROYS Python whitespace.[/yellow]")
            console.print("[yellow]The output code may have INVALID INDENTATION/SYNTAX.[/yellow]")
            console.print("[bold yellow]" + "=" * 60 + "[/bold yellow]")
            console.print("")
            
            # Perform legacy scrape
            clean_pattern = r"\\"
            cleaned_text = re.sub(clean_pattern, "", full_text)
            
            block_pattern = r"--- START_FILE: (.*?) ---\n(.*?)--- END_FILE ---"
            matches = re.findall(block_pattern, cleaned_text, re.DOTALL)
            
            if not matches:
                console.print("[bold red]✗ No files found via text scraping either.[/bold red]")
                raise typer.Exit(code=1)
                
            for filename, content in matches:
                filename = filename.strip()
                if len(filename) > 200 or "\n" in filename: 
                    continue
                    
                full_out_path = os.path.join(output_dir, filename)
                
                try:
                    os.makedirs(os.path.dirname(full_out_path), exist_ok=True)
                    with open(full_out_path, 'w', encoding='utf-8') as f:
                        f.write(content.strip())
                    files_restored += 1
                    console.print(f"  [yellow]⚠ Scraped: {filename}[/yellow]")
                except Exception as e:
                    console.print(f"  [red]Failed to save {filename}: {e}[/red]")

            console.print(f"\n[bold yellow]⚠️ Emergency Extraction Complete:[/bold yellow] {files_restored} files recovered (LOSSY).")
            console.print("[dim]Please manually verify indentation before using this code.[/dim]")
        else:
            # Safe Abort (Protect User from Silent Corruption)
            console.print("")
            console.print("[bold red]" + "=" * 60 + "[/bold red]")
            console.print("[bold red][!] RESTORATION ABORTED to protect codebase integrity.[/bold red]")
            console.print("[bold red]" + "=" * 60 + "[/bold red]")
            console.print("")
            console.print("The Digital Twin manifest is missing or corrupted.")
            console.print("Automatic fallback to text scraping has been DISABLED")
            console.print("because it produces syntactically invalid Python code.")
            console.print("")
            console.print("If you understand the risks and need partial recovery,")
            console.print("run again with the emergency flag:")
            console.print("")
            console.print(f"    [bold]vibecode unpack \"{pdf_path}\" --force-scrape[/bold]")
            console.print("")
            raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]✗ Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="gui", help="Launch the interactive GUI for project management.")
def launch_gui():
    """
    Launch the PyQt6 GUI for interactive project management.
    """
    console.print("[bold cyan]Launching GUI...[/bold cyan]")
    try:
        run_gui()
    except Exception as e:
        console.print(f"[bold red]✗ Error launching GUI:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command(name="serve", help="Run Vibecode as an MCP server for external AI agents.")
def run_server(
    port: int = typer.Option(
        8080, "--port", "-p",
        help="Port to run the MCP server on."
    ),
    project: str = typer.Option(
        None, "--project",
        help="Project root directory for tool operations."
    )
):
    """
    Run Vibecode as an MCP Server.
    
    Extension 6: Exposes Vibecode's capabilities as MCP tools for external AI agents
    like Claude Desktop, Cursor, or any MCP-compatible client.
    
    Available tools:
    - snapshot_codebase: Generate PDF snapshots
    - search_files: Search for files
    - read_file: Read file contents
    - list_files: List directory contents
    - get_project_summary: Get project statistics
    """
    console.print(
        Panel.fit(
            f"[bold green]🚀 Starting Vibecode MCP Server[/bold green]\n"
            f"Port: {port}\n"
            f"Project: {project or 'Current directory'}",
            border_style="green"
        )
    )
    
    try:
        from .mcp_server import run_server as start_mcp
        start_mcp(port=port, project_root=project)
    except ImportError as e:
        console.print(f"[bold red]✗ MCP Server not available:[/bold red] {e}")
        console.print("[dim]Install with: pip install mcp[server][/dim]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]✗ Server error:[/bold red] {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()