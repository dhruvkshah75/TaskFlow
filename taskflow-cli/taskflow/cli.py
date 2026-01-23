import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from .auth import save_token, delete_token, get_token
from .api import api_request
import os
from pathlib import Path
import json

# initialise the app and console
app = typer.Typer(help="TaskFlow CLI - Manage your tasks from the terminal") 
console = Console()


@app.command()
def register(
    email: str = typer.Option(..., "--email", "-e", prompt=True, help="Your email address"),
    username: str = typer.Option(..., "--username", "-u", prompt=True, help="Your username"),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True, help="Your password")
):
    """Register a new TaskFlow account."""
    console.print("\n[bold cyan]Creating your TaskFlow account...[/]")
    
    data = {
        "email": email,
        "username": username,
        "password": password
    }
    
    response = api_request("POST", "/users/", json=data)
    
    if response is None:
        console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")
    elif response.status_code == 201:
        user_data = response.json()
        console.print(f"\n[bold green]✓[/] Account created successfully!")
        console.print(f"[dim]User ID:[/] {user_data['id']}")
        console.print(f"[dim]Username:[/] {user_data['username']}")
        console.print(f"[dim]Email:[/] {user_data['email']}")
        console.print("\n[yellow]→[/] You can now login with: [bold]login[/]")
    else:
        try:
            error = response.json().get("detail", "Registration failed")
        except:
            error = "Registration failed"
        console.print(f"\n[bold red]✗[/] {error}")


@app.command()
def login(
    identifier: str = typer.Option(..., "--identifier", "-i", prompt=True, help="Your email or username"),
    password: str = typer.Option(..., "--password", "-p", prompt=True, hide_input=True, help="Your password")
):
    """Login to your TaskFlow account."""
    console.print("\n[bold cyan]Logging in...[/]")
    
    data = {
        "identifier": identifier,
        "password": password
    }
    
    response = api_request("POST", "/login", json=data)
    
    if response is None:
        console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")
    elif response.status_code == 200:
        token_data = response.json()
        save_token(token_data["access_token"])
        console.print("\n[bold green]✓[/] Login successful!")
        console.print("[dim]Your session has been saved securely.[/]")
    else:
        # Handle error responses (403, 401, etc.)
        try:
            error = response.json().get("detail", "Login failed")
        except:
            error = "Login failed"
        console.print(f"\n[bold red]✗[/] {error}")


@app.command()
def logout():
    """Logout from your TaskFlow account."""
    if not get_token():
        console.print("[yellow]You are not logged in.[/]")
        return
    
    if Confirm.ask("\n[bold yellow]Are you sure you want to logout?[/]"):
        delete_token()  # deleting the token will not allow the user to make any commands
        console.print("\n[bold green]✓[/] Logged out successfully!")
    else:
        console.print("[dim]Logout cancelled.[/]")


@app.command()
def upload_file(
    file_path: str = typer.Argument(..., help="Path to the Python file to upload"),
    title: str = typer.Option(..., "--title", "-t", help="Task title/name for this file")
):
    """Upload a Python task file to TaskFlow."""
    if not get_token():
        console.print("[bold red]✗[/] You must be logged in to upload files.")
        console.print("[dim]Run:[/] taskflow login")
        return
    
    file_path_obj = Path(file_path)
    
    if not file_path_obj.exists():
        console.print(f"[bold red]✗[/] File not found: {file_path}")
        return
    
    if not file_path_obj.suffix == ".py":
        console.print("[bold red]✗[/] Only Python (.py) files are allowed")
        return
    
    console.print(f"\n[bold cyan]Uploading task file...[/]")
    console.print(f"[dim]File:[/] {file_path_obj.name}")
    console.print(f"[dim]Title:[/] {title}")
    
    with open(file_path_obj, "rb") as f:
        files = {"file": (file_path_obj.name, f, "text/x-python")}
        params = {"file_name": title}
        
        response = api_request("POST", "/tasks/upload_file", files=files, params=params)
    
    if response is None:

    
        console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")

    
    elif response.status_code == 201:
        result = response.json()
        console.print(f"\n[bold green]✓[/] {result['message']}")
        console.print(f"\n[yellow]→[/] You can now create tasks with title: [bold]{title}[/]")
    elif response:
        error = response.json().get("detail", "Upload failed")
        console.print(f"\n[bold red]✗[/] Upload failed: {error}")
    else:
        console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")


@app.command()
def create_task(
    title: str = typer.Option(..., "--title", "-t", help="Task title (must match uploaded file)"),
    payload: str = typer.Option(..., "--payload", "-p", help="Task payload data"),
    scheduled_at: int = typer.Option(0, "--scheduled-at", "-s", help="Schedule task in N minutes from now")
):
    """Create a new task."""
    if not get_token():
        console.print("[bold red]✗[/] You must be logged in to create tasks.")
        console.print("[dim]Run:[/] taskflow login")
        return
    
    console.print(f"\n[bold cyan]Creating task...[/]")
    
    data = {
        "title": title,
        "payload": payload,
        "scheduled_at": scheduled_at
    }
    
    response = api_request("POST", "/tasks/", json=data)
    
    if response is None:
        console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")
    elif response.status_code == 201:
        task = response.json()
        console.print(f"\n[bold green]✓[/] Task created successfully!")
        console.print(f"[dim]Task ID:[/] {task['id']}")
        console.print(f"[dim]Title:[/] {task['title']}")
        console.print(f"[dim]Status:[/] {task['status']}")
        console.print(f"[dim]Scheduled:[/] {task['scheduled_at']}")
    else:
        try:
            error = response.json().get("detail", "Task creation failed")
        except:
            error = "Task creation failed"
        console.print(f"\n[bold red]✗[/] {error}")


@app.command()
def list_tasks(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of tasks to retrieve"),
    skip: int = typer.Option(0, "--skip", help="Number of tasks to skip"),
    search: str = typer.Option("", "--search", "-s", help="Search tasks by title"),
    status: str = typer.Option(None, "--status", help="Filter by status: pending, processing, completed, failed")
):
    """List all your tasks."""
    if not get_token():
        console.print("[bold red]✗[/] You must be logged in to view tasks.")
        console.print("[dim]Run:[/] taskflow login")
        return
    
    console.print(f"\n[bold cyan]Fetching your tasks...[/]")
    
    params = {
        "limit": limit,
        "skip": skip,
        "search": search
    }
    if status:
        params["status"] = status
    
    response = api_request("GET", "/tasks/", params=params)
    
    if response is None:

    
        console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")

    
    elif response.status_code == 200:
        tasks = response.json()
        
        if not tasks:
            console.print("\n[yellow]No tasks found.[/]")
            return
        
        table = Table(title=f"\n[bold]Your Tasks[/] ({len(tasks)} found)")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Created At", style="blue")
        table.add_column("Scheduled At", style="yellow")
        
        for task in tasks:
            table.add_row(
                str(task["id"]),
                task["title"],
                task["status"],
                task["created_at"][:19],
                task["scheduled_at"][:19]
            )
        
        console.print(table)
    elif response:
        error = response.json().get("detail", "Failed to fetch tasks")
        console.print(f"\n[bold red]✗[/] Failed to fetch tasks: {error}")
    else:
        console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")


@app.command()
def get_task(task_id: int = typer.Argument(..., help="Task ID to retrieve")):
    """Get details of a specific task."""
    if not get_token():
        console.print("[bold red]✗[/] You must be logged in to view tasks.")
        console.print("[dim]Run:[/] taskflow login")
        return
    
    console.print(f"\n[bold cyan]Fetching task {task_id}...[/]")
    
    response = api_request("GET", f"/tasks/{task_id}")
    
    if response is None:

    
        console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")

    
    elif response.status_code == 200:
        task = response.json()
        
        console.print(f"\n[bold]Task Details[/]")
        console.print(f"[cyan]ID:[/] {task['id']}")
        console.print(f"[cyan]Title:[/] {task['title']}")
        console.print(f"[cyan]Status:[/] {task['status']}")
        console.print(f"[cyan]Owner ID:[/] {task['owner_id']}")
        console.print(f"[cyan]Created At:[/] {task['created_at']}")
        console.print(f"[cyan]Scheduled At:[/] {task['scheduled_at']}")
    elif response and response.status_code == 404:
        console.print(f"\n[bold red]✗[/] Task with ID {task_id} not found")
    elif response:
        error = response.json().get("detail", "Failed to fetch task")
        console.print(f"\n[bold red]✗[/] Failed to fetch task: {error}")
    else:
        console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")


@app.command()
def delete_task(task_id: int = typer.Argument(..., help="Task ID to delete")):
    """Delete a specific task."""
    if not get_token():
        console.print("[bold red]✗[/] You must be logged in to delete tasks.")
        console.print("[dim]Run:[/] taskflow login")
        return
    
    if not Confirm.ask(f"\n[bold yellow]Are you sure you want to delete task {task_id}?[/]"):
        console.print("[dim]Deletion cancelled.[/]")
        return
    
    console.print(f"\n[bold cyan]Deleting task {task_id}...[/]")
    
    response = api_request("DELETE", f"/tasks/{task_id}")
    
    if response is None:

    
        console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")

    
    elif response.status_code == 204:
        console.print(f"\n[bold green]✓[/] Task {task_id} deleted successfully!")
    elif response and response.status_code == 404:
        console.print(f"\n[bold red]✗[/] Task with ID {task_id} not found")
    elif response and response.status_code == 401:
        console.print(f"\n[bold red]✗[/] Not authorized to delete this task")
    elif response:
        error = response.json().get("detail", "Failed to delete task")
        console.print(f"\n[bold red]✗[/] Failed to delete task: {error}")
    else:
        console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")


@app.command()
def delete_file(
    title: str = typer.Option(..., "--title", "-t", help="Task file title to delete")
):
    """Delete a task file from the server."""
    if not get_token():
        console.print("[bold red]✗[/] You must be logged in to delete files.")
        console.print("[dim]Run:[/] taskflow login")
        return
    
    if not Confirm.ask(f"\n[bold yellow]Are you sure you want to delete task file '{title}.py'?[/]"):
        console.print("[dim]Deletion cancelled.[/]")
        return
    
    console.print(f"\n[bold cyan]Deleting task file...[/]")
    
    params = {"file_name": title}
    response = api_request("DELETE", "/tasks/delete_file", params=params)
    
    if response is None:

    
        console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")

    
    elif response.status_code == 200:
        result = response.json()
        console.print(f"\n[bold green]✓[/] {result['message']}")
    elif response and response.status_code == 404:
        console.print(f"\n[bold red]✗[/] Task file '{title}.py' not found")
    elif response:
        error = response.json().get("detail", "Failed to delete file")
        console.print(f"\n[bold red]✗[/] Failed to delete file: {error}")
    else:
        console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")


@app.command()
def whoami():
    """Display current login status."""
    token = get_token()
    
    if token:
        console.print("\n[bold green]✓[/] You are logged in")
        console.print(f"[dim]Token stored securely in system keyring[/]")
        
        # Try to get user info
        response = api_request("GET", "/tasks/", params={"limit": 1})
        if response is None:

            console.print("\n[bold red]✗[/] Could not connect to TaskFlow API")

        elif response.status_code == 200:
            console.print("[dim]Connection to API: Active[/]")
        else:
            console.print("[yellow]Warning: Token may be expired or invalid[/]")
    else:
        console.print("\n[yellow]You are not logged in[/]")
        console.print("[dim]Run:[/] taskflow login")


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    api_url: str = typer.Option(None, "--api-url", help="Set the API URL")
):
    """Configure CLI settings."""
    config_file = Path.home() / ".taskflow" / "config.json"
    config_file.parent.mkdir(exist_ok=True)
    
    if show:
        if config_file.exists():
            with open(config_file, "r") as f:
                cfg = json.load(f)
            console.print("\n[bold]Current Configuration:[/]")
            for key, value in cfg.items():
                console.print(f"  [cyan]{key}:[/] {value}")
        else:
            console.print("\n[yellow]No configuration file found[/]")
            console.print(f"[dim]Default API URL:[/] {os.getenv('TASKFLOW_API_URL', 'http://localhost:8000')}")
        return
    
    if api_url:
        cfg = {}
        if config_file.exists():
            with open(config_file, "r") as f:
                cfg = json.load(f)
        
        cfg["api_url"] = api_url
        os.environ["TASKFLOW_API_URL"] = api_url
        
        with open(config_file, "w") as f:
            json.dump(cfg, f, indent=2)
        
        console.print(f"\n[bold green]✓[/] API URL set to: {api_url}")

