# Comfy Node Ledger

A lightweight ComfyUI utility node that records the parameter values of any
nodes you choose — every time your workflow runs successfully.

**Version:** 1.5.4

---

## What it does

Each time ComfyUI completes a run, Comfy Node Ledger reads the live values
from your selected nodes and parameters, then:

- Writes a neatly formatted `.md` (or `.txt`) log you can open in any editor
- Optionally writes a `.json` file for scripted processing
- Outputs the same formatted text as a string so you can plug it into any
  display node in your workflow

Files are versioned automatically (`MyLog_v001.md`, `MyLog_v002.md`, …)
so nothing ever overwrites a previous run.

---

## Installation

1. Clone or copy this folder into your ComfyUI custom nodes directory:

```
ComfyUI/
  custom_nodes/
    comfy_node_ledger/   ← place here
      __init__.py
      node.py
      ...
```

2. Restart ComfyUI (or reload custom nodes).

3. Find **Comfy Node Ledger** under the `utils` category in the node menu.

---

## Node inputs

| Field | Required | Description |
|---|---|---|
| `filename_prefix` | ✅ | Save path + filename stem, e.g. `outputs/MyWorkflowLog`. The last token after `/` becomes the filename. A bare string (no `/`) saves to ComfyUI's default output directory. |
| `header` | — | Optional text shown at the top of the log, under the title. |
| `export_json` | — | Toggle: write a `.json` file alongside the log. Default on. |
| `export_log` | — | Toggle: write the `.md` / `.txt` log file. Default on. |
| `log_format` | — | `md` (default) or `txt`. |
| `comments` | — | Optional free-text notes appended at the end of the log. |
| `footer` | — | Optional single-line note placed at the very end of the log. |
| `node_preset` | — | Connect the `node_preset` output of another Ledger node here to chain them (see Chaining). |
| `wait_for` | — | Connect any node here to force Ledger to execute after it. |

---

## Watch table

The centre of the node is the **watch table**. Each row represents one node
you want to track.

- Click **+ Add node** to add a row.
- In the left dropdown, choose any node from your workflow.
- Checkboxes for that node's parameters appear on the right — tick the ones
  you want to record.
- Click **−** to remove a row.

Up to **40 rows** per Ledger instance. To track more nodes, chain a second
Ledger instance (see below).

---

## Node outputs

| Output | Type | Description |
|---|---|---|
| `display_text` | STRING | The formatted log text. Plug into any display/text node. |
| `node_preset` | NODE_PRESET | Accumulated data — plug into the next Ledger instance when chaining. |
| `fileprefix_out` | STRING | The `filename_prefix` value passed through, for reuse. |

---

## Output file format

```
MyWorkflowLog
-------------------------------------------
Header text goes here

[KSampler :: My Sampler :: 12]
  seed    : 42
  denoise : 0.75
  steps   : 20

[CLIPTextEncode :: Positive Prompt :: 7]
  text    : a beautiful sunset over mountains, golden hour lighting

-------------------------------------------
Footer note

Comments:
  Batch 3 — reduced denoise for sharper output.
```

The `.json` export contains the same data in machine-readable form:

```json
{
  "ledger_version": "1.0.0",
  "filename_prefix": "outputs/MyWorkflowLog",
  "header": "Header text goes here",
  "footer": "Footer note",
  "comments": "Batch 3 — reduced denoise for sharper output.",
  "nodes": [
    {
      "node_id": "12",
      "class_type": "KSampler",
      "label": "My Sampler",
      "params": {
        "seed": 42,
        "denoise": 0.75,
        "steps": 20
      }
    }
  ]
}
```

---

## Chaining multiple instances

If you need to watch more than 40 nodes, or want to split your tracking
across logical groups, you can chain Ledger nodes:

```
[Ledger A] --node_preset--> [Ledger B] --node_preset--> [Ledger C]
```

- Each instance watches its own set of nodes independently.
- The chain accumulates all entries and writes **one unified file** from
  the last instance in the chain.
- Only the **last** instance needs `export_log` / `export_json` enabled —
  or leave them all on and each will write its own versioned file.
- Use `fileprefix_out` from the first instance to keep paths consistent
  across all chained nodes.

---

## Parameters wired from other nodes

If a parameter's value comes from another node (e.g. a Float node feeding
CFG, or a String node feeding a prompt), Ledger follows the link back to
the source and records the actual value — not a placeholder.

---

## Troubleshooting

**"filename_prefix is required" error**
: Fill in the `filename_prefix` field before running.

**"Permission denied" error**
: ComfyUI does not have write access to the target path. Use a path inside
  ComfyUI's output directory, or grant write permissions to the target folder.

**Watch table dropdown is empty**
: The node list is populated from the live graph. Make sure other nodes
  exist in the workflow before adding rows to the Ledger.

**Values show `(not captured)`**
: The parameter exists on the node but was not present in the prompt graph
  at execution time. This can happen with unconnected optional inputs.

---
