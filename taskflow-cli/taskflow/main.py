import typer
import time
import sys
import signal
from rich.console import Console
from .cli import app as cli_app

console = Console()
app = typer.Typer()

# Track CTRL+C presses
ctrl_c_count = 0
last_ctrl_c_time = 0

# Register all CLI commands
app.add_typer(cli_app, name="", help="TaskFlow CLI commands")


def signal_handler(sig, frame):
    """Handle CTRL+C gracefully with double-press confirmation."""
    global ctrl_c_count, last_ctrl_c_time
    
    current_time = time.time()
    
    # Reset counter if more than 2 seconds passed since last CTRL+C
    if current_time - last_ctrl_c_time > 2:
        ctrl_c_count = 0
    
    ctrl_c_count += 1
    last_ctrl_c_time = current_time
    
    if ctrl_c_count == 1:
        console.print("\n[yellow]Press CTRL+C again within 2 seconds to exit[/]")
    else:
        console.print("\n[bold red]Exiting TaskFlow CLI...[/]")
        sys.exit(0)


# Register signal handler
signal.signal(signal.SIGINT, signal_handler)


def typewriter_print(text: str, delay: float = 0.04):
    """Simulates a typewriter transition for terminal text."""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
        time.sleep(delay)
    print()


def display_splash():
    # ASCII Art for TASKFLOW
    ascii_logo = """
 ████████╗ █████╗ ███████╗██╗  ██╗███████╗██╗      ██████╗ ██╗    ██╗
 ╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝██╔════╝██║     ██╔═══██╗██║    ██║
    ██║   ███████║███████╗█████═╝ █████╗  ██║     ██║   ██║██║ █╗ ██║
    ██║   ██╔══██║╚════██║██╔═██╗ ██╔══╝  ██║     ██║   ██║██║███╗██║
    ██║   ██║  ██║███████║██║  ██╗██║     ███████╗╚██████╔╝╚███╔███╔╝
    ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝ 
    """

    console.print(f"[orange_red1]{ascii_logo}[/orange_red1]")
    
    # Version and Subtitle
    console.print(" [bold white]v2.1.0[/bold white] | [dim]Distributed Task Orchestrator[/dim]\n")

    # Personalized Typewriter Greeting
    typewriter_print("> Connection established. Ready to process tasks", delay=0.003)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """TaskFlow CLI - Distributed Task Orchestrator"""
    if ctx.invoked_subcommand is None:
        display_splash()
        console.print("\n[bold cyan]Quick Start:[/]")
        console.print("  [bold]register[/]              - Create a new account")
        console.print("  [bold]login[/]                 - Login to your account")
        console.print("  [bold]upload-file[/]           - Upload a task Python file")
        console.print("  [bold]create-task[/]           - Create a new task")
        console.print("  [bold]list-tasks[/]            - View all your tasks")
        console.print("\n[dim]Type a command or [bold]help[/bold] to see all commands.")
        console.print("[dim italic]Press CTRL+C twice to exit[/dim italic]\n")
        
        # Enter interactive mode
        interactive_mode()


def interactive_mode():
    """Run CLI in interactive loop mode."""
    import shlex
    from rich.prompt import Confirm
    from rich.table import Table
    
    while True:
        try:
            # Prompt for command
            user_input = console.input("[bold cyan]taskflow>[/] ")
            
            if not user_input.strip():
                continue
            
            # Handle built-in commands
            if user_input.strip().lower() in ['exit', 'quit']:
                if Confirm.ask("\n[bold yellow]Are you sure you want to exit?[/]"):
                    console.print("[bold green]Goodbye![/]")
                    sys.exit(0)
                continue
            
            if user_input.strip().lower() == 'clear':
                console.clear()
                continue
            
            if user_input.strip().lower() in ['help', '--help', '-h']:
                display_help()
                continue
            
            # Parse the command
            args = shlex.split(user_input)
            
            # Execute the command by invoking the main app with args
            try:
                # Save original argv
                original_argv = sys.argv.copy()
                
                # Set new argv with the command
                sys.argv = ['taskflow'] + args
                
                # Invoke the app
                try:
                    app(args, standalone_mode=False)
                except SystemExit:
                    pass
                
                # Restore original argv
                sys.argv = original_argv
                    
            except Exception as e:
                # Restore argv on error
                sys.argv = original_argv
                console.print(f"[bold red]Error:[/] {str(e)}")
                console.print("[dim]Type 'help' to see available commands[/]")
        
        except KeyboardInterrupt:
            # Let the global handler deal with it
            signal_handler(signal.SIGINT, None)
        except EOFError:
            console.print("\n[bold red]Exiting TaskFlow CLI...[/]")
            sys.exit(0)


def display_help():
    """Display help menu with all available commands."""
    from rich.table import Table
    
    console.print("\n[bold cyan]TaskFlow CLI - Available Commands[/]\n")
    
    # Single table with all commands
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Command", style="cyan", no_wrap=True, width=45)
    table.add_column("Description", style="white")
    
    # Authentication commands
    table.add_row("[bold yellow]Authentication[/]", "")
    table.add_row("register", "Create a new TaskFlow account")
    table.add_row("login", "Login to your account")
    table.add_row("logout", "Logout from your account")
    
    # Task management commands
    table.add_row("", "")
    table.add_row("[bold yellow]Task Management[/]", "")
    table.add_row("create-task --title <name> --payload <data>", "Create a new task")
    table.add_row("  --scheduled-at <minutes>", "  Schedule task in N minutes (default: 0)")
    table.add_row("list-tasks", "List all your tasks")
    table.add_row("  --limit <number>", "  Number of tasks to show (default: 10)")
    table.add_row("  --skip <number>", "  Skip first N tasks (default: 0)")
    table.add_row("  --search <keyword>", "  Search tasks by title")
    table.add_row("  --status <status>", "  Filter by status (pending/processing/completed/failed)")
    table.add_row("get-task <id>", "Get details of a specific task")
    table.add_row("delete-task <id>", "Delete a task")
    
    # File management commands
    table.add_row("", "")
    table.add_row("[bold yellow]File Management[/]", "")
    table.add_row("upload-file <filepath> --title <name>", "Upload a Python task file")
    table.add_row("  <filepath>", "  Path to the .py file to upload")
    table.add_row("  --title <name> (required)", "  Task name to use when creating tasks")
    table.add_row("delete-file --title <name>", "Delete an uploaded task file")
    
    # Built-in commands
    table.add_row("", "")
    table.add_row("[bold yellow]Built-in Commands[/]", "")
    table.add_row("help", "Show this help message")
    table.add_row("clear", "Clear the screen")
    table.add_row("exit / quit", "Exit the CLI")
    
    console.print(table)
    console.print()
    
    console.print("[dim]For detailed help on a command, use: [bold]<command> --help[/bold][/dim]")
    console.print("[dim]Example: [bold]register --help[/bold] or [bold]upload-file --help[/bold][/dim]\n")


def run():
    """Entry point for the CLI."""
    try:
        app()
    except KeyboardInterrupt:
        # This catches any unhandled CTRL+C
        console.print("\n[bold red]Exiting TaskFlow CLI...[/]")
        sys.exit(0)


if __name__ == "__main__":
    run()