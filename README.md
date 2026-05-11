# AgentContract MCP Server

**Smart contracts between AI agents.** A Model Context Protocol (MCP) server for creating, managing, and enforcing binding agreements between AI agents with formal deliverables, deadlines, penalties, and a full lifecycle state machine.

## Pricing

**$19/month** — [Subscribe via Stripe](https://buy.stripe.com/dRm6oJ4Hd2Jugek0wz1oI0m)

## Features

- 🤝 **Create contracts** between two agents with deliverables, deadlines, payment, and milestones
- ✍️ **Sign contracts** — both parties must sign to activate
- 📋 **Full contract lifecycle**: draft → pending_signatures → active → completed / breached / terminated
- 📝 **Propose amendments** to active contracts
- 🚨 **Report breaches** with full audit trail
- 🔍 **Query contracts** and inspect status history
- 💾 **Persistent storage** — all contracts stored as JSON in `~/.agentcontracts/`

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Running the Server (stdio mode)

```bash
python server.py
```

The server communicates via **STDIO transport** and is designed to be launched by an MCP client (e.g., Claude Desktop, VS Code, or any MCP-compatible host).

### MCP Client Configuration

Add to your MCP client config:

```json
{
  "mcpServers": {
    "agent-contract": {
      "command": "python",
      "args": ["/path/to/agent-contract-mcp/server.py"]
    }
  }
}
```

## Tools

### 1. `contract_create`

Create a new binding agreement between two agents.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `parties` | `[string, string]` | ✅ | Two agent IDs |
| `terms.deliverables` | `[string]` | ✅ | List of deliverables |
| `terms.deadline` | `string` (ISO 8601) | ✅ | Delivery deadline |
| `terms.payment_amount` | `number` | ✅ | Payment amount |
| `terms.milestones` | `[string]` | ❌ | Optional milestones |
| `penalties.late_penalty` | `number` | ✅ | Late delivery penalty |
| `penalties.failure_penalty` | `number` | ✅ | Failure penalty |

**Example:**
```json
{
  "parties": ["agent-alpha", "agent-beta"],
  "terms": {
    "deliverables": ["Research report on Q2 market trends", "Executive summary"],
    "deadline": "2026-06-01T00:00:00Z",
    "payment_amount": 5000,
    "milestones": ["Draft by May 15", "Final by June 1"]
  },
  "penalties": {
    "late_penalty": 100,
    "failure_penalty": 2500
  }
}
```

**Returns:** `contract_id`, `status: "draft"`

---

### 2. `contract_get`

Retrieve the full contract with all terms, signatures, amendments, and status history.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `contract_id` | `string` | ✅ | UUID of the contract |

**Returns:** Complete contract object.

---

### 3. `contract_sign`

Sign a contract on behalf of an agent. The contract transitions through the lifecycle:
- **1st signature**: `draft` → `pending_signatures`
- **2nd signature**: `pending_signatures` → `active`

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `contract_id` | `string` | ✅ | UUID of the contract |
| `agent_id` | `string` | ✅ | Agent performing the signature |

**Constraints:**
- Agent must be a party to the contract
- Each agent can sign only once
- Contract must be in `draft` or `pending_signatures` status

---

### 4. `contract_amend`

Propose an amendment to an active contract. Amendments are recorded but do not automatically modify the original terms.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `contract_id` | `string` | ✅ | UUID of the contract |
| `proposing_agent` | `string` | ✅ | Agent proposing the change |
| `changes` | `object` | ✅ | Amendment details |
| `changes.description` | `string` | ✅ | Description of changes |
| `changes.modified_terms` | `object` | ❌ | Modified term values |
| `changes.modified_penalties` | `object` | ❌ | Modified penalty values |

**Constraints:**
- Contract must be in `active` status
- Proposing agent must be a party to the contract

---

### 5. `contract_status`

Get the current lifecycle status of a contract with full history.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `contract_id` | `string` | ✅ | UUID of the contract |

**Returns:** Status, human-readable description, parties, signatures, amendment count, breach record, and full status history timeline.

---

### 6. `contract_report_breach`

Report a breach of contract. Transitions status from `active` to `breached`.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `contract_id` | `string` | ✅ | UUID of the contract |
| `breached_by` | `string` | ✅ | Agent that breached |
| `details` | `string` | ✅ | Description of the breach |

**Constraints:**
- Contract must be in `active` status
- Breached agent must be a party to the contract

## Contract Lifecycle

```
                  ┌──────────┐
                  │   draft   │
                  └─────┬─────┘
                        │ 1st signature
                  ┌─────▼──────────┐
                  │ pending_signatures│
                  └─────┬──────────┘
                        │ 2nd signature
                  ┌─────▼────┐
                  │  active   │
                  └──┬───┬───┘
                     │   │
          ┌──────────┘   └──────────┐
          ▼                         ▼
    ┌──────────┐              ┌──────────┐
    │ completed│              │ breached  │
    └──────────┘              └──────────┘

    Any non-terminated state can transition to:
    ┌───────────┐
    │ terminated│
    └───────────┘
```

## Storage

All contracts are stored as individual JSON files in `~/.agentcontracts/`.

```
~/.agentcontracts/
├── <contract-uuid-1>.json
├── <contract-uuid-2>.json
└── ...
```

Each file contains the complete contract state including terms, signatures, amendments, breach records, and full status history.

## Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Run the server
python server.py
```

## License

MIT
