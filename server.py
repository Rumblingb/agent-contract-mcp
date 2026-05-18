"""
AgentContract MCP Server
========================
A Model Context Protocol (MCP) server for creating and managing binding
agreements between AI agents. Supports the full contract lifecycle:
draft -> pending_signatures -> active -> completed -> breached -> terminated.

Storage: JSON files in ~/.agentcontracts/
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mcp.server.lowlevel import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import Tool, TextContent, ErrorData
from mcp.shared.exceptions import McpError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STORAGE_DIR = os.path.expanduser("~/.agentcontracts")
VALID_STATUSES = ["draft", "pending_signatures", "active", "completed", "breached", "terminated"]
VALID_TRANSITIONS: Dict[str, List[str]] = {
    "draft":               ["pending_signatures", "terminated"],
    "pending_signatures":  ["active", "terminated"],
    "active":              ["completed", "breached", "terminated"],
    "completed":           [],
    "breached":            [],
    "terminated":          [],
}

# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _ensure_storage():
    """Create the storage directory if it doesn't exist."""
    os.makedirs(STORAGE_DIR, exist_ok=True)


def _contract_path(contract_id: str) -> str:
    return os.path.join(STORAGE_DIR, f"{contract_id}.json")


def _load_contract(contract_id: str) -> Optional[Dict[str, Any]]:
    path = _contract_path(contract_id)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def _save_contract(contract: Dict[str, Any]):
    _ensure_storage()
    path = _contract_path(contract["contract_id"])
    with open(path, "w") as f:
        json.dump(contract, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------

server = Server("agent-contract-server")


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="contract_create",
            description=(
                "Create a new binding agreement between two agents. "
                "Returns the contract_id on success. "
                "Initial status is 'draft'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "parties": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 2,
                        "description": "Two agent IDs that are parties to the contract",
                    },
                    "terms": {
                        "type": "object",
                        "properties": {
                            "deliverables": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of deliverables/obligations",
                            },
                            "deadline": {
                                "type": "string",
                                "description": "ISO 8601 deadline timestamp",
                            },
                            "payment_amount": {
                                "type": "number",
                                "description": "Payment amount for the contract",
                            },
                            "milestones": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Optional list of milestones",
                            },
                        },
                        "required": ["deliverables", "deadline", "payment_amount"],
                    },
                    "penalties": {
                        "type": "object",
                        "properties": {
                            "late_penalty": {
                                "type": "number",
                                "description": "Penalty for late delivery",
                            },
                            "failure_penalty": {
                                "type": "number",
                                "description": "Penalty for failure to deliver",
                            },
                        },
                        "required": ["late_penalty", "failure_penalty"],
                        "description": "Penalty terms for the contract",
                    },
                },
                "required": ["parties", "terms", "penalties"],
            },
        ),
        Tool(
            name="contract_get",
            description=(
                "Retrieve a full contract by its ID, including all terms, "
                "signatures, amendments, and status history."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "string",
                        "description": "UUID of the contract to retrieve",
                    },
                },
                "required": ["contract_id"],
            },
        ),
        Tool(
            name="contract_sign",
            description=(
                "Sign a contract on behalf of an agent. Both parties must sign "
                "before the contract transitions from 'draft'/'pending_signatures' "
                "to 'active'. An agent can only sign once."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "string",
                        "description": "UUID of the contract to sign",
                    },
                    "agent_id": {
                        "type": "string",
                        "description": "Agent ID performing the signature",
                    },
                },
                "required": ["contract_id", "agent_id"],
            },
        ),
        Tool(
            name="contract_amend",
            description=(
                "Propose an amendment to an existing contract. The amendment is "
                "recorded on the contract but does not change the original terms — "
                "it is a proposed change that agents can review. Amendments can "
                "only be proposed while the contract is in 'active' status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "string",
                        "description": "UUID of the contract to amend",
                    },
                    "proposing_agent": {
                        "type": "string",
                        "description": "Agent ID proposing the amendment",
                    },
                    "changes": {
                        "type": "object",
                        "description": "Description of changes being proposed (freeform object)",
                        "properties": {
                            "description": {
                                "type": "string",
                                "description": "Human-readable description of the amendment",
                            },
                            "modified_terms": {
                                "type": "object",
                                "description": "Modified term values",
                            },
                            "modified_penalties": {
                                "type": "object",
                                "description": "Modified penalty values",
                            },
                        },
                        "required": ["description"],
                    },
                },
                "required": ["contract_id", "proposing_agent", "changes"],
            },
        ),
        Tool(
            name="contract_status",
            description=(
                "Get the current lifecycle status of a contract. Returns the "
                "status, a human-readable state, and timestamps for status "
                "transitions. Status flow: draft -> pending_signatures -> "
                "active -> completed | breached | terminated."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "string",
                        "description": "UUID of the contract",
                    },
                },
                "required": ["contract_id"],
            },
        ),
        Tool(
            name="contract_report_breach",
            description=(
                "Report a breach of contract by one of the parties. This "
                "transitions the contract status to 'breached' and records "
                "the breach details including which agent breached and when."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "contract_id": {
                        "type": "string",
                        "description": "UUID of the breached contract",
                    },
                    "breached_by": {
                        "type": "string",
                        "description": "Agent ID that breached the contract",
                    },
                    "details": {
                        "type": "string",
                        "description": "Description of the breach",
                    },
                },
                "required": ["contract_id", "breached_by", "details"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    _ensure_storage()

    if name == "contract_create":
        return [await _handle_contract_create(arguments)]
    elif name == "contract_get":
        return [await _handle_contract_get(arguments)]
    elif name == "contract_sign":
        return [await _handle_contract_sign(arguments)]
    elif name == "contract_amend":
        return [await _handle_contract_amend(arguments)]
    elif name == "contract_status":
        return [await _handle_contract_status(arguments)]
    elif name == "contract_report_breach":
        return [await _handle_contract_report_breach(arguments)]
    else:
        raise McpError(ErrorData(code=-32601, message=f"Unknown tool: {name}"))


# ---------------------------------------------------------------------------
# Contract Creation
# ---------------------------------------------------------------------------

async def _handle_contract_create(args: dict) -> TextContent:
    parties = args["parties"]
    terms = args["terms"]
    penalties = args["penalties"]

    if len(parties) != 2:
        raise McpError(ErrorData(code=-32602, message="Exactly two parties are required"))

    agent1, agent2 = parties[0], parties[1]
    if agent1 == agent2:
        raise McpError(ErrorData(code=-32602, message="Parties must be distinct agents"))

    contract_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    contract = {
        "contract_id": contract_id,
        "status": "draft",
        "parties": [agent1, agent2],
        "terms": {
            "deliverables": terms.get("deliverables", []),
            "deadline": terms["deadline"],
            "payment_amount": terms["payment_amount"],
            "milestones": terms.get("milestones", []),
        },
        "penalties": {
            "late_penalty": penalties["late_penalty"],
            "failure_penalty": penalties["failure_penalty"],
        },
        "signatures": {},
        "amendments": [],
        "breach_record": None,
        "status_history": [
            {"status": "draft", "timestamp": now, "note": "Contract created"},
        ],
        "created_at": now,
        "updated_at": now,
    }

    _save_contract(contract)

    return TextContent(
        type="text",
        text=json.dumps({
            "success": True,
            "contract_id": contract_id,
            "status": "draft",
            "message": f"Contract {contract_id} created between {agent1} and {agent2}",
        }, indent=2),
    )


# ---------------------------------------------------------------------------
# Contract Get
# ---------------------------------------------------------------------------

async def _handle_contract_get(args: dict) -> TextContent:
    contract_id = args["contract_id"]
    contract = _load_contract(contract_id)

    if contract is None:
        raise McpError(ErrorData(code=-32602, message=f"Contract not found: {contract_id}"))

    return TextContent(
        type="text",
        text=json.dumps(contract, indent=2, default=str),
    )


# ---------------------------------------------------------------------------
# Contract Sign
# ---------------------------------------------------------------------------

async def _handle_contract_sign(args: dict) -> TextContent:
    contract_id = args["contract_id"]
    agent_id = args["agent_id"]

    contract = _load_contract(contract_id)
    if contract is None:
        raise McpError(ErrorData(code=-32602, message=f"Contract not found: {contract_id}"))

    if contract["status"] not in ("draft", "pending_signatures"):
        raise McpError(
            ErrorData(
                code=-32603,
                message=f"Cannot sign contract in status '{contract['status']}'. Must be 'draft' or 'pending_signatures'.",
            )
        )

    if agent_id not in contract["parties"]:
        raise McpError(
            ErrorData(code=-32602, message=f"Agent '{agent_id}' is not a party to this contract")
        )

    if agent_id in contract["signatures"]:
        raise McpError(
            ErrorData(code=-32603, message=f"Agent '{agent_id}' has already signed this contract")
        )

    now = datetime.now(timezone.utc).isoformat()
    contract["signatures"][agent_id] = {"agent_id": agent_id, "signed_at": now}
    contract["updated_at"] = now

    # If this is the first signature, move to pending_signatures
    if contract["status"] == "draft":
        contract["status"] = "pending_signatures"
        contract["status_history"].append({
            "status": "pending_signatures",
            "timestamp": now,
            "note": f"Signed by {agent_id} — waiting for second party",
        })

    # If both parties have signed, activate
    if len(contract["signatures"]) == 2:
        contract["status"] = "active"
        contract["status_history"].append({
            "status": "active",
            "timestamp": now,
            "note": f"All parties signed — contract is now active",
        })

    _save_contract(contract)

    return TextContent(
        type="text",
        text=json.dumps({
            "success": True,
            "contract_id": contract_id,
            "agent": agent_id,
            "status": contract["status"],
            "signatures": len(contract["signatures"]),
            "message": f"Agent '{agent_id}' signed contract {contract_id}. Status: {contract['status']}",
        }, indent=2),
    )


# ---------------------------------------------------------------------------
# Contract Amend
# ---------------------------------------------------------------------------

async def _handle_contract_amend(args: dict) -> TextContent:
    contract_id = args["contract_id"]
    proposing_agent = args["proposing_agent"]
    changes = args["changes"]

    contract = _load_contract(contract_id)
    if contract is None:
        raise McpError(ErrorData(code=-32602, message=f"Contract not found: {contract_id}"))

    if contract["status"] != "active":
        raise McpError(
            ErrorData(
                code=-32603,
                message=f"Cannot amend contract in status '{contract['status']}'. Only 'active' contracts can be amended.",
            )
        )

    if proposing_agent not in contract["parties"]:
        raise McpError(
            ErrorData(code=-32602, message=f"Agent '{proposing_agent}' is not a party to this contract")
        )

    now = datetime.now(timezone.utc).isoformat()
    amendment = {
        "amendment_id": str(uuid.uuid4()),
        "proposed_by": proposing_agent,
        "changes": changes,
        "proposed_at": now,
        "status": "proposed",
    }

    contract["amendments"].append(amendment)
    contract["updated_at"] = now

    _save_contract(contract)

    return TextContent(
        type="text",
        text=json.dumps({
            "success": True,
            "contract_id": contract_id,
            "amendment_id": amendment["amendment_id"],
            "proposed_by": proposing_agent,
            "message": f"Amendment proposed by {proposing_agent} on contract {contract_id}",
        }, indent=2),
    )


# ---------------------------------------------------------------------------
# Contract Status
# ---------------------------------------------------------------------------

async def _handle_contract_status(args: dict) -> TextContent:
    contract_id = args["contract_id"]

    contract = _load_contract(contract_id)
    if contract is None:
        raise McpError(ErrorData(code=-32602, message=f"Contract not found: {contract_id}"))

    status_descriptions = {
        "draft": "Contract has been drafted but not yet signed by any party.",
        "pending_signatures": "One party has signed; waiting for the second party to sign.",
        "active": "Both parties have signed. Contract is in force.",
        "completed": "All deliverables have been fulfilled and the contract is complete.",
        "breached": "A party has breached the terms of the contract.",
        "terminated": "The contract has been terminated before completion.",
    }

    result = {
        "contract_id": contract_id,
        "status": contract["status"],
        "description": status_descriptions.get(contract["status"], ""),
        "parties": contract["parties"],
        "signatures": list(contract["signatures"].keys()),
        "amendment_count": len(contract["amendments"]),
        "breach_record": contract.get("breach_record"),
        "status_history": contract["status_history"],
        "created_at": contract["created_at"],
        "updated_at": contract["updated_at"],
    }

    return TextContent(
        type="text",
        text=json.dumps(result, indent=2, default=str),
    )


# ---------------------------------------------------------------------------
# Contract Report Breach
# ---------------------------------------------------------------------------

async def _handle_contract_report_breach(args: dict) -> TextContent:
    contract_id = args["contract_id"]
    breached_by = args["breached_by"]
    details = args["details"]

    contract = _load_contract(contract_id)
    if contract is None:
        raise McpError(ErrorData(code=-32602, message=f"Contract not found: {contract_id}"))

    if contract["status"] != "active":
        raise McpError(
            ErrorData(
                code=-32603,
                message=f"Cannot report breach on contract in status '{contract['status']}'. Only 'active' contracts can be breached.",
            )
        )

    if breached_by not in contract["parties"]:
        raise McpError(
            ErrorData(code=-32602, message=f"Agent '{breached_by}' is not a party to this contract")
        )

    now = datetime.now(timezone.utc).isoformat()
    breach_record = {
        "breached_by": breached_by,
        "details": details,
        "reported_at": now,
    }

    contract["status"] = "breached"
    contract["breach_record"] = breach_record
    contract["status_history"].append({
        "status": "breached",
        "timestamp": now,
        "note": f"Breach reported: {breached_by} — {details}",
    })
    contract["updated_at"] = now

    _save_contract(contract)

    return TextContent(
        type="text",
        text=json.dumps({
            "success": True,
            "contract_id": contract_id,
            "breached_by": breached_by,
            "status": "breached",
            "message": f"Breach reported: {breached_by} breached contract {contract_id}",
        }, indent=2),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the AgentContract MCP server via stdio transport."""
    import anyio

    async def _run():
        async with server.run(
            read_stream=server.stdio_read(),
            write_stream=server.stdio_write(),
            initialization_options=InitializationOptions(
                server_name="agent-contract-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        ):
            await server.wait_for_shutdown()

    anyio.run(_run)


if __name__ == "__main__":
    main()
