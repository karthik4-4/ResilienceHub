"""
StateGraph Builder for SCDRC Multi-Agent Blackboard Coordination.
"""

from __future__ import annotations
from langgraph.graph import StateGraph, START, END

from scdrc.graph.state import BlackboardGraphState
from scdrc.graph.nodes import (
    monitor_node,
    inventory_node,
    supplier_node,
    route_node,
    cost_node,
    coordinator_node,
    notify_node,
)


def create_disruption_graph() -> StateGraph:
    """
    Constructs the LangGraph StateGraph governing multi-agent disruption response.
    Topology:
      START
        │
      monitor
       ├───┬───┐ (Parallel fan-out)
       │   │   │
      inv supp route
       └───┼───┘ (Fan-in)
           │
         cost
           │
      coordinator
           │
        notify
           │
          END
    """
    workflow = StateGraph(BlackboardGraphState)

    # 1. Add all 6 specialist agent nodes + notification node
    workflow.add_node("monitor", monitor_node)
    workflow.add_node("inventory", inventory_node)
    workflow.add_node("supplier", supplier_node)
    workflow.add_node("route", route_node)
    workflow.add_node("cost", cost_node)
    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("notify", notify_node)

    # 2. Add sequential and fan-out/fan-in edges
    workflow.add_edge(START, "monitor")
    workflow.add_edge("monitor", "inventory")
    workflow.add_edge("monitor", "supplier")
    workflow.add_edge("monitor", "route")

    workflow.add_edge("inventory", "cost")
    workflow.add_edge("supplier", "cost")
    workflow.add_edge("route", "cost")

    workflow.add_edge("cost", "coordinator")
    workflow.add_edge("coordinator", "notify")
    workflow.add_edge("notify", END)

    return workflow


def get_compiled_disruption_app():
    """Returns a compiled, executable LangGraph application."""
    workflow = create_disruption_graph()
    return workflow.compile()
