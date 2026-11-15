"""
Command Line Interface (CLI) for SCDRC.
Provides commands: run, eval, serve, ui.
"""

from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from scdrc.core.orchestrator import Orchestrator
from scdrc.core.config import load_settings
from scdrc.data.seed import seed_database
from scdrc.retrieval.ingest import ingest_documents

console = Console()


def run_command(args: argparse.Namespace) -> None:
    settings = load_settings()
    orchestrator = Orchestrator(settings=settings)

    report_text = args.report
    failure_injection = {}

    if args.scenario:
        scenarios_dir = Path(settings.paths.scenarios_dir)
        clean_scen = args.scenario.strip()
        matching = list(scenarios_dir.glob(f"*{clean_scen}*.json"))
        if not matching:
            num_str = "".join([c for c in clean_scen if c.isdigit()])
            if num_str:
                num = int(num_str)
                matching = list(scenarios_dir.glob(f"*_{num:02d}.json")) or list(scenarios_dir.glob(f"*_{num}.json"))
        if not matching:
            console.print(f"[bold red]Scenario '{args.scenario}' not found in {scenarios_dir}[/bold red]")
            sys.exit(1)
        with open(matching[0], "r", encoding="utf-8") as f:
            scen = json.load(f)
            report_text = scen["report_text"]
            console.print(f"[bold cyan]Running Scripted Scenario: {scen.get('name')} ({args.scenario})[/bold cyan]")
            if args.scenario == "S10" or "scenario_10" in matching[0].name:
                failure_injection["timeout_agent"] = "inventory"

    if not report_text:
        console.print("[bold red]Error: Either --report or --scenario must be provided.[/bold red]")
        sys.exit(1)

    console.print(f"\n[bold yellow]Ingesting Report:[/bold yellow] {report_text}\n")
    with console.status("[bold green]Coordinating Multi-Agent Response via Blackboard...[/bold green]"):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                orchestrator.run_case(report_text, failure_injection=failure_injection)
            )
        finally:
            loop.close()

    dec = result["decision"]
    action_color = "green" if dec["action"] == "REORDER" else ("blue" if dec["action"] == "REROUTE" else "yellow")

    console.print(Panel(
        f"[bold {action_color}]ACTION: {dec['action']}[/bold {action_color}]\n"
        f"[bold]Chosen Option:[/bold] {dec['chosen_option']}\n"
        f"[bold]Total Landed Cost:[/bold] INR {dec['total_cost_inr']:,.2f}\n"
        f"[bold]Confidence:[/bold] {dec['confidence'] * 100:.1f}%\n\n"
        f"[bold]Rationale:[/bold]\n{dec['rationale']}\n\n"
        f"[bold]Cited Blackboard Entries:[/bold] {', '.join(dec['cited_entries'])}",
        title=f"Mitigation Decision (Case: {result['case_id']})",
        border_style=action_color,
    ))

    # Notifications Table
    notif_table = Table(title="Dispatched Stakeholder Notifications")
    notif_table.add_column("Role", style="cyan")
    notif_table.add_column("Recipient", style="white")
    notif_table.add_column("Channel", style="magenta")
    notif_table.add_column("Urgency", style="red")

    for n in result.get("notify", []):
        notif_table.add_row(n["role"], n.get("name", "N/A"), n["channel"].upper(), n["urgency"].upper())

    console.print(notif_table)
    console.print(f"\n[bold green]Blackboard Snapshot saved at:[/bold green] {result['blackboard_snapshot']}")


def eval_command(args: argparse.Namespace) -> None:
    """Run full evaluation suite across all 10 scenarios."""
    from tests.eval.run_eval import run_evaluation_suite
    run_evaluation_suite()


def serve_command(args: argparse.Namespace) -> None:
    """Launch FastAPI server."""
    import uvicorn
    console.print(f"[bold green]Starting SCDRC REST API on http://{args.host}:{args.port}...[/bold green]")
    uvicorn.run("scdrc.api.main:app", host=args.host, port=args.port, reload=args.reload)


def ui_command(args: argparse.Namespace) -> None:
    """Launch Streamlit web dashboard."""
    import subprocess
    dash_path = Path(__file__).parent / "ui" / "dashboard.py"
    console.print(f"[bold green]Starting Streamlit Dashboard on port {args.port}...[/bold green]")
    subprocess.run(["streamlit", "run", str(dash_path), "--server.port", str(args.port)])


def init_command(args: argparse.Namespace) -> None:
    """Initialize database and vector store."""
    settings = load_settings()
    console.print("[bold green]Seeding database...[/bold green]")
    seed_database(settings.paths.database_url.replace("sqlite:///", ""), settings.paths.seed_dir)
    console.print("[bold green]Ingesting RAG documents into ChromaDB...[/bold green]")
    ingest_documents(docs_dir="./data/documents", persist_dir=settings.paths.chroma_persist_dir)
    console.print("[bold cyan]System initialization complete![/bold cyan]")


def main() -> None:
    parser = argparse.ArgumentParser(description="SCDRC Multi-Agent Blackboard CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run command
    run_parser = subparsers.add_parser("run", help="Run disruption response coordination")
    run_parser.add_argument("--report", "-r", type=str, help="Disruption report text")
    run_parser.add_argument("--scenario", "-s", type=str, help="Scripted scenario ID (e.g. S1, S2, ..., S10)")

    # eval command
    subparsers.add_parser("eval", help="Run evaluation harness across all 10 scenarios")

    # init command
    subparsers.add_parser("init", help="Seed database and ingest documents")

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start FastAPI REST server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host address")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port number")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # ui command
    ui_parser = subparsers.add_parser("ui", help="Start Streamlit web dashboard")
    ui_parser.add_argument("--port", type=int, default=8501, help="Port number")

    args = parser.parse_args()
    if args.command == "run":
        run_command(args)
    elif args.command == "eval":
        eval_command(args)
    elif args.command == "init":
        init_command(args)
    elif args.command == "serve":
        serve_command(args)
    elif args.command == "ui":
        ui_command(args)


if __name__ == "__main__":
    main()
