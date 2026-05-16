/**
 * ledger_widgets.js
 * Comfy Node Ledger - frontend widget registration
 *
 * Version: 1.5.4
 *
 *
 */

import { app } from "../../scripts/app.js";

// ---Constants ---

const BLOCKED_TYPES = new Set([
  "ComfyNodeLedger",
  "ForLoopOpen", "ForLoopClose",
  "WhileLoopOpen", "WhileLoopClose",
  "AccumulateNode", "FlowManipulator",
]);

// Widget names ComfyUI strips from the server prompt - injected from JS at queue time.
const UI_ONLY_WIDGET_NAMES = new Set([
  "control_after_generate",
  "control_after_generate_1",
]);

// Node types whose full content lives only in the frontend (never in the prompt).
const NOTE_CLASS_TYPES = new Set(["Note", "NoteNode", "MarkdownNote"]);

// Preview widget names - not yet filtered, reserved for a future version.
const PREVIEW_WIDGET_NAMES = new Set([
  "$$canvas-image-preview",
  "video-preview",
  "image_preview",
]);

const MAX_WATCH_ROWS       = 40;
const TABLE_MAX_HEIGHT_PX  = 180;
const TABLE_MIN_HEIGHT_PX  = 72;   // row height

// ---Helpers ---

function getLiveNodes(graph) {
  return (graph._nodes || []).filter(
    (n) => !BLOCKED_TYPES.has(n.type) && n.id !== undefined
  );
}

function getWidgetDescriptors(graphNode) {
  if (!graphNode?.widgets) return [];
  return graphNode.widgets
    .filter((w) => w.type !== "button" && w.name)
    .map((w) => ({ name: w.name }));
}

/**
 * Read live injected values at queue time only - never at checkbox-tick time.
 */
function readLiveInjected(graphNode, paramNames) {
  if (!graphNode?.widgets) return null;
  const isNoteNode = NOTE_CLASS_TYPES.has(graphNode.type);
  const result = {};
  for (const w of graphNode.widgets) {
    if (!paramNames.includes(w.name)) continue;
    if (UI_ONLY_WIDGET_NAMES.has(w.name) || isNoteNode) {
      result[w.name] = w.value ?? null;
    }
  }
  return Object.keys(result).length > 0 ? result : null;
}

function nodeLabel(n) {
  const title = n.title && n.title !== n.type ? n.title : "";
  return title ? `${n.type} :: ${title} :: ${n.id}` : `${n.type} :: ${n.id}`;
}

function _btnStyle(extra) {
  const base = [
    "font-size:11px", "padding:2px 8px", "border-radius:4px", "cursor:pointer",
    "border:1px solid var(--border-color,#555)",
    "background:var(--comfy-input-bg,#2a2a2a)",
    "color:var(--input-text,#ddd)",
  ].join(";");
  return extra ? base + ";" + extra : base;
}

function _hintSpan(text) {
  const s = document.createElement("span");
  s.textContent = text;
  s.style.cssText = "font-size:10px;opacity:0.4;";
  return s;
}

function _wrap(originalFn, afterFn) {
  return function (...args) {
    originalFn?.apply(this, args);
    afterFn(args[0]);
  };
}

/**
 * Position a floating list element using fixed coordinates derived from
 * its anchor element's bounding rect. This escapes any scroll/clip container.
 */
function _positionFixed(listEl, anchorEl) {
  const rect = anchorEl.getBoundingClientRect();
  listEl.style.top    = `${rect.bottom + 2}px`;
  listEl.style.left   = `${rect.left}px`;
  listEl.style.width  = `${rect.width}px`;
}

// ---SearchableDropdown ---

class SearchableDropdown {
  constructor(onSelect, initialNodeId = null) {
    this._onSelect   = onSelect;
    this._selectedId = initialNodeId;
    this._isOpen     = false;
    this.el          = this._build();
    if (initialNodeId) this._applySelection(initialNodeId);
  }

  _build() {
    const wrapper = document.createElement("div");
    wrapper.style.cssText = "position:relative;flex:1;min-width:0;";

    this._input = document.createElement("input");
    this._input.type        = "text";
    this._input.placeholder = "Search nodes…";
    this._input.style.cssText = [
      "width:100%", "box-sizing:border-box", "font-size:11px",
      "background:var(--comfy-input-bg,#2a2a2a)",
      "color:var(--input-text,#ddd)",
      "border:1px solid var(--border-color,#555)",
      "border-radius:4px", "padding:2px 6px", "cursor:pointer", "outline:none",
    ].join(";");

    // Fixed-position list - escapes the scroll container
    this._list = document.createElement("div");
    this._list.style.cssText = [
      "position:fixed",
      "z-index:99999",
      "background:var(--comfy-menu-bg,#1e1e1e)",
      "border:1px solid var(--border-color,#555)",
      "border-radius:4px",
      "max-height:200px", "overflow-y:auto", "overflow-x:hidden",
      "scrollbar-width:thin",
      "display:none",
    ].join(";");
    document.body.appendChild(this._list);

    wrapper.appendChild(this._input);

    this._input.addEventListener("focus", () => this._open());
    this._input.addEventListener("click", () => this._open());
    this._input.addEventListener("input", () => this._filter(this._input.value));
    this._input.addEventListener("keydown", (e) => {
      if (e.key === "Escape") this._close(false);
    });
    wrapper.addEventListener("focusout", (e) => {
      if (!wrapper.contains(e.relatedTarget) && !this._list.contains(e.relatedTarget)) {
        setTimeout(() => {
          if (!wrapper.contains(document.activeElement) &&
              !this._list.contains(document.activeElement)) {
            this._close(false);
          }
        }, 120);
      }
    });

    return wrapper;
  }

  _open() {
    if (this._isOpen) return;
    this._isOpen = true;
    this._input.value = "";
    this._renderList(getLiveNodes(app.graph));
    _positionFixed(this._list, this._input);
    this._list.style.display = "block";
    this._input.select();
  }

  _close(didSelect) {
    if (!this._isOpen) return;
    this._isOpen = false;
    this._list.style.display = "none";
    if (!didSelect) this._applySelection(this._selectedId);
  }

  _renderList(nodes) {
    this._list.innerHTML = "";
    this._list.appendChild(this._makeItem(null, "- none -"));
    if (nodes.length === 0) {
      const empty = document.createElement("div");
      empty.textContent = "(no nodes found)";
      empty.style.cssText = "font-size:10px;opacity:0.4;padding:4px 8px;";
      this._list.appendChild(empty);
      return;
    }
    for (const n of nodes) {
      this._list.appendChild(this._makeItem(String(n.id), nodeLabel(n)));
    }
  }

  _makeItem(nodeId, label) {
    const item = document.createElement("div");
    item.textContent = label;
    item.style.cssText = [
      "font-size:11px", "padding:4px 8px", "cursor:pointer",
      "white-space:nowrap", "overflow:hidden", "text-overflow:ellipsis",
      nodeId === this._selectedId ? "background:var(--comfy-input-bg,#3a3a3a);font-weight:600;" : "",
    ].join(";");
    item.addEventListener("mouseenter", () => item.style.background = "var(--comfy-input-bg,#3a3a3a)");
    item.addEventListener("mouseleave", () => {
      item.style.background = nodeId === this._selectedId ? "var(--comfy-input-bg,#3a3a3a)" : "";
    });
    item.addEventListener("mousedown", (e) => {
      e.preventDefault();
      this._select(nodeId, label);
    });
    return item;
  }

  _filter(query) {
    const q = query.trim().toLowerCase();
    const nodes = getLiveNodes(app.graph);
    const matched = q ? nodes.filter((n) => nodeLabel(n).toLowerCase().includes(q)) : nodes;
    this._renderList(matched);
    _positionFixed(this._list, this._input);  // reposition in case layout shifted
  }

  _select(nodeId) {
    this._selectedId = nodeId;
    this._close(true);
    this._applySelection(nodeId);
    this._onSelect(nodeId);
  }

  _applySelection(nodeId) {
    if (!nodeId) { this._input.value = ""; return; }
    const n = app.graph._nodes?.find((n) => String(n.id) === String(nodeId));
    this._input.value = n ? nodeLabel(n) : nodeId;
  }

  refresh() {
    if (this._isOpen) {
      this._filter(this._input.value);
    }
    this._applySelection(this._selectedId);
  }

  get selectedId() { return this._selectedId; }
}

// ---ParamDropdown ---
//
// Compact param selector: shows a summary line when closed, a floating
// checkbox list when open. Uses position:fixed to escape the scroll container.
//
//  Closed:  [ 2 selected: seed, denoise  dropdown ]
//  Open:    floating list with checkboxes

class ParamDropdown {
  /**
   * @param {Set<string>}                  selectedParams  initial ticked params
   * @param {function(Set<string>): void}  onChange        fired on any tick change
   */
  constructor(selectedParams, onChange) {
    this._selected = new Set(selectedParams);
    this._onChange = onChange;
    this._isOpen   = false;
    this._names    = [];
    this.el        = this._build();
  }

  _build() {
    const wrapper = document.createElement("div");
    wrapper.style.cssText = "position:relative;min-width:110px;max-width:200px;flex:1;";

    this._summary = document.createElement("div");
    this._summary.tabIndex = 0;
    this._summary.style.cssText = [
      "font-size:11px",
      "background:var(--comfy-input-bg,#2a2a2a)",
      "color:var(--input-text,#ddd)",
      "border:1px solid var(--border-color,#555)",
      "border-radius:4px", "padding:2px 6px", "cursor:pointer",
      "white-space:nowrap", "overflow:hidden", "text-overflow:ellipsis",
      "user-select:none",
    ].join(";");
    this._updateSummary();

    // Fixed-position list - escapes the scroll container
    this._list = document.createElement("div");
    this._list.style.cssText = [
      "position:fixed",
      "z-index:99999",
      "background:var(--comfy-menu-bg,#1e1e1e)",
      "border:1px solid var(--border-color,#555)",
      "border-radius:4px",
      "max-height:200px", "overflow-y:auto",
      "scrollbar-width:thin",
      "display:none",
    ].join(";");
    document.body.appendChild(this._list);

    wrapper.appendChild(this._summary);

    this._summary.addEventListener("click",   (e) => { e.stopPropagation(); this._toggle(); });
    this._summary.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this._toggle(); }
      if (e.key === "Escape") this._close();
    });

    // Close when user clicks anywhere outside the summary or the floating list.
    // Using document-level click is more reliable than focusout for fixed-position
    
    this._outsideClickHandler = (e) => {
      if (!wrapper.contains(e.target) && !this._list.contains(e.target)) {
        this._close();
      }
    };

    return wrapper;
  }

  _toggle() { this._isOpen ? this._close() : this._open(); }

  _open() {
    if (this._isOpen) return;
    this._isOpen = true;
    this._renderList();
    _positionFixed(this._list, this._summary);
    this._list.style.display = "block";
    // Defer attachment so the click that opened us doesn't immediately close us
    setTimeout(() => document.addEventListener("click", this._outsideClickHandler), 0);
  }

  _close() {
    if (!this._isOpen) return;
    this._isOpen = false;
    this._list.style.display = "none";
    document.removeEventListener("click", this._outsideClickHandler);
  }

  _renderList() {
    this._list.innerHTML = "";
    if (this._names.length === 0) {
      const hint = document.createElement("div");
      hint.textContent = "(no params)";
      hint.style.cssText = "font-size:10px;opacity:0.4;padding:4px 8px;";
      this._list.appendChild(hint);
      return;
    }

    // ---Select all / Deselect all row ---
    const allRow = document.createElement("label");
    allRow.style.cssText = [
      "display:flex", "align-items:center", "gap:6px",
      "padding:3px 8px", "cursor:pointer", "font-size:11px",
      "white-space:nowrap", "border-bottom:1px solid var(--border-color,#555)",
      "margin-bottom:2px",
    ].join(";");
    allRow.addEventListener("mouseenter", () => allRow.style.background = "var(--comfy-input-bg,#3a3a3a)");
    allRow.addEventListener("mouseleave", () => allRow.style.background = "");

    const allCb = document.createElement("input");
    allCb.type = "checkbox";
    allCb.style.cssText = "margin:0;cursor:pointer;flex-shrink:0;";
    // Reflect current state: checked if all selected, indeterminate if some
    const allSelected  = this._names.every(n => this._selected.has(n));
    const noneSelected = this._names.every(n => !this._selected.has(n));
    allCb.checked       = allSelected;
    allCb.indeterminate = !allSelected && !noneSelected;

    allCb.addEventListener("change", () => {
      if (allCb.checked) {
        this._names.forEach(n => this._selected.add(n));
      } else {
        this._names.forEach(n => this._selected.delete(n));
      }
      this._updateSummary();
      this._onChange(new Set(this._selected));
      // Re-render to sync individual checkboxes
      this._renderList();
    });

    allRow.appendChild(allCb);
    allRow.appendChild(document.createTextNode("Select all"));
    this._list.appendChild(allRow);

    // ---Individual param checkboxes ---
    for (const name of this._names) {
      const row = document.createElement("label");
      row.style.cssText = [
        "display:flex", "align-items:center", "gap:6px",
        "padding:3px 8px", "cursor:pointer", "font-size:11px", "white-space:nowrap",
      ].join(";");
      row.addEventListener("mouseenter", () => row.style.background = "var(--comfy-input-bg,#3a3a3a)");
      row.addEventListener("mouseleave", () => row.style.background = "");

      const cb = document.createElement("input");
      cb.type    = "checkbox";
      cb.checked = this._selected.has(name);
      cb.style.cssText = "margin:0;cursor:pointer;flex-shrink:0;";
      cb.addEventListener("change", () => {
        if (cb.checked) this._selected.add(name);
        else            this._selected.delete(name);
        this._updateSummary();
        this._onChange(new Set(this._selected));
        // Update the Select all checkbox state without full re-render
        const nowAll  = this._names.every(n => this._selected.has(n));
        const nowNone = this._names.every(n => !this._selected.has(n));
        allCb.checked       = nowAll;
        allCb.indeterminate = !nowAll && !nowNone;
      });

      row.appendChild(cb);
      row.appendChild(document.createTextNode(name));
      this._list.appendChild(row);
    }
  }

  _updateSummary() {
    const count = this._selected.size;
    if (count === 0) {
      this._summary.textContent = "Select params ▾";
      this._summary.style.opacity = "0.45";
    } else {
      this._summary.textContent = `${count} selected: ${[...this._selected].join(", ")} ▾`;
      this._summary.style.opacity = "1";
    }
  }

  setNames(names) {
    this._names    = names;
    this._selected = new Set([...this._selected].filter(n => names.includes(n)));
    this._updateSummary();
    if (this._isOpen) this._renderList();
  }

  setSelected(params) {
    this._selected = new Set(params);
    this._updateSummary();
    if (this._isOpen) this._renderList();
  }

  get selected() { return new Set(this._selected); }
}

// ---WatchTable ---

class WatchTable {
  constructor(node, hiddenWidget) {
    this.node         = node;
    this.hiddenWidget = hiddenWidget;
    this.rows         = [];
    this.container    = this._buildContainer();
  }

  _buildContainer() {
    const el = document.createElement("div");
    el.className = "cnl-table";
    el.style.cssText = "display:flex;flex-direction:column;gap:4px;padding:4px 0;";

    const header = document.createElement("div");
    header.style.cssText =
      "display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;";

    const labelEl = document.createElement("span");
    labelEl.textContent = "Watch table";
    labelEl.style.cssText =
      "font-size:11px;font-weight:600;opacity:0.65;text-transform:uppercase;letter-spacing:.04em;";

    const addBtn = document.createElement("button");
    addBtn.textContent = "+ Add node";
    addBtn.style.cssText = _btnStyle();
    addBtn.addEventListener("click", () => this._addRow());

    header.appendChild(labelEl);
    header.appendChild(addBtn);
    el.appendChild(header);

    this.rowsContainer = document.createElement("div");
    this.rowsContainer.style.cssText = [
      "display:flex", "flex-direction:column", "gap:4px",
      `min-height:${TABLE_MIN_HEIGHT_PX}px`,
      `max-height:${TABLE_MAX_HEIGHT_PX}px`,
      "overflow-y:auto", "overflow-x:hidden",
      "scrollbar-width:thin", "padding-right:2px",
    ].join(";");

    el.appendChild(this.rowsContainer);
    return el;
  }

  _buildRow(index) {
    const row = this.rows[index];

    const rowEl = document.createElement("div");
    rowEl.style.cssText = [
      "display:flex", "gap:4px", "align-items:center",
      "background:var(--comfy-input-bg,#2a2a2a)",
      "border-radius:6px", "padding:4px 6px", "min-width:0",
    ].join(";");

    // ---Right: ParamDropdown (created first so node dropdown can drive it) ---
    const paramDropdown = new ParamDropdown(row.params, (newSelected) => {
      row.params = newSelected;
      this._serialise();
    });
    row._paramDropdown = paramDropdown;

    // Pre-populate param names if a node is already selected (e.g. on restore)
    if (row.nodeId) {
      const graphNode = app.graph._nodes.find(
        (n) => String(n.id) === String(row.nodeId)
      );
      if (graphNode) {
        paramDropdown.setNames(getWidgetDescriptors(graphNode).map(d => d.name));
      }
    }

    // ---Left: SearchableDropdown ---
    const nodeDropdown = new SearchableDropdown((nodeId) => {
      row.nodeId = nodeId || null;
      row.params = new Set();
      row._dropdown = nodeDropdown;

      if (nodeId) {
        const graphNode = app.graph._nodes.find(
          (n) => String(n.id) === String(nodeId)
        );
        const names = graphNode ? getWidgetDescriptors(graphNode).map(d => d.name) : [];
        paramDropdown.setNames(names);
        paramDropdown.setSelected(new Set());
      } else {
        paramDropdown.setNames([]);
        paramDropdown.setSelected(new Set());
      }
      row.params = paramDropdown.selected;
      this._serialise();
    }, row.nodeId);

    row._dropdown = nodeDropdown;

    // ---Remove button ---
    const removeBtn = document.createElement("button");
    removeBtn.textContent = "−";
    removeBtn.title = "Remove this row";
    removeBtn.style.cssText = _btnStyle("flex-shrink:0;padding:2px 6px;");
    removeBtn.addEventListener("click", () => {
      this.rows.splice(index, 1);
      this._rebuildRows();
      this._serialise();
    });

    rowEl.appendChild(nodeDropdown.el);
    rowEl.appendChild(paramDropdown.el);
    rowEl.appendChild(removeBtn);
    return rowEl;
  }

  _refreshParamArea(row) {
    if (!row._paramDropdown || !row.nodeId) {
      row._paramDropdown?.setNames([]);
      return;
    }
    const graphNode = app.graph._nodes.find(
      (n) => String(n.id) === String(row.nodeId)
    );
    const names = graphNode ? getWidgetDescriptors(graphNode).map(d => d.name) : [];
    row._paramDropdown.setNames(names);
  }

  _addRow() {
    if (this.rows.length >= MAX_WATCH_ROWS) {
      alert(
        `Comfy Node Ledger: max ${MAX_WATCH_ROWS} rows per instance reached.\n` +
        "Chain another Ledger node to watch more."
      );
      return;
    }
    this.rows.push({ nodeId: null, params: new Set() });
    this._rebuildRows();
  }

  _rebuildRows() {
    this.rowsContainer.innerHTML = "";
    for (let i = 0; i < this.rows.length; i++) {
      this.rowsContainer.appendChild(this._buildRow(i));
    }
    this.node.setDirtyCanvas(true);
  }

  _refreshDropdowns() {
    for (const row of this.rows) {
      row._dropdown?.refresh();
      this._refreshParamArea(row);
    }
  }

  // ---Serialisation ---
  // r.params is always the source of truth: it is updated directly by
  // ParamDropdown's onChange callback, so it is always current.

  _serialise() {
    const payload = this.rows
      .filter((r) => r.nodeId && r.params.size > 0)
      .map((r) => {
        const graphNode = app.graph._nodes.find(
          (n) => String(n.id) === String(r.nodeId)
        );
        return {
          node_id:    r.nodeId,
          params:     [...r.params],
          class_type: graphNode?.type  ?? "",
          label:      graphNode?.title ?? "",
        };
      });
    this.hiddenWidget.value = JSON.stringify(payload);
  }

  buildLivePayload() {
    const stable = JSON.parse(this.hiddenWidget.value || "[]");
    return stable.map((entry) => {
      const graphNode = app.graph._nodes.find(
        (n) => String(n.id) === String(entry.node_id)
      );
      const injected = graphNode
        ? readLiveInjected(graphNode, entry.params)
        : null;
      const out = { ...entry };
      if (injected) out.injected = injected;
      return out;
    });
  }

  restore(jsonStr) {
    try {
      const specs = JSON.parse(jsonStr || "[]");
      this.rows = specs.map((s) => ({
        nodeId: String(s.node_id),
        params: new Set(s.params || []),
      }));
    } catch (_) {
      this.rows = [];
    }
    this._rebuildRows();
  }
}

// ---Extension registration ---

const _activeTables = new WeakMap();

app.registerExtension({
  name: "ComfyNodeLedger.WatchTable",

  async nodeCreated(node) {
    if (node.comfyClass !== "ComfyNodeLedger") return;

    // ---1. Find and suppress the watched_nodes widget ---
    //
    // CRITICAL: the widget MUST stay in node.widgets so ComfyUI includes its
    // value when serialising the prompt. We suppress its visual rendering only.
    // We never create a detached fake object - that breaks prompt serialisation.

    let hiddenWidget = node.widgets?.find((w) => w.name === "watched_nodes");

    if (hiddenWidget) {
      hiddenWidget.type        = "hidden";
      hiddenWidget.computeSize = () => [0, -4];
      hiddenWidget.draw        = () => {};
      if (hiddenWidget.inputEl) {
        hiddenWidget.inputEl.style.display = "none";
        hiddenWidget.inputEl.remove();
      }
      // Move to end of widgets array (keeps it in the array for ComfyUI,
      // but ComfyUI renders widgets in order so moving it last minimises gap)
      const idx = node.widgets.indexOf(hiddenWidget);
      if (idx !== -1) {
        node.widgets.splice(idx, 1);
        node.widgets.push(hiddenWidget);
      }
    } else {
      // Widget not present yet - happens on first node creation before
      // ComfyUI has processed INPUT_TYPES. Create a minimal stand-in that
      // ComfyUI will not render but will read during prompt serialisation.
      hiddenWidget = { name: "watched_nodes", value: "[]", type: "hidden",
                       computeSize: () => [0, -4], draw: () => {} };
      node.widgets = node.widgets || [];
      node.widgets.push(hiddenWidget);
    }

    // ---2. Constrain Comments multiline box height ---
    // We constrain both the DOM element (CSS maxHeight) AND the widget's computeSize, so LiteGraph allocates only the capped height in its layout.
    // Without the computeSize cap, LiteGraph over-allocates and the surplus
    // appears as a gap between the comments field and the watch table below it.
    setTimeout(() => {
      const commentsWidget = node.widgets?.find((w) => w.name === "comments");
      if (commentsWidget?.inputEl) {
        const el = commentsWidget.inputEl;
        el.style.maxHeight = "60px";
        el.style.minHeight = "36px";
        el.style.overflowY = "auto";
        el.style.resize    = "none";
      }
      // Cap LiteGraph's layout allocation for the comments widget.
      // 60px content + ~10px padding = 70px max. Without this, LiteGraph keeps allocating the widget's natural expanded height on resize.
      if (commentsWidget) {
        const _origComputeSize = commentsWidget.computeSize?.bind(commentsWidget);
        commentsWidget.computeSize = (width) => {
          const orig = _origComputeSize ? _origComputeSize(width) : [width, 70];
          return [orig[0], Math.min(orig[1], 70)];
        };
      }
    }, 80);

    // ---3. Build and inject the WatchTable DOM widget ---
    const table = new WatchTable(node, hiddenWidget);
    _activeTables.set(node, table);

    if (hiddenWidget.value && hiddenWidget.value !== "[]") {
      setTimeout(() => table.restore(hiddenWidget.value), 140);
    }

    node.addDOMWidget("cnl_watch_table", "div", table.container, {
      getValue: () => hiddenWidget.value,
      setValue: (v) => table.restore(v),
    });

    // ---4. Graph topology change hooks ---
    app.graph.onNodeAdded = _wrap(app.graph.onNodeAdded, () => {
      table._refreshDropdowns();
    });

    app.graph.onNodeRemoved = _wrap(app.graph.onNodeRemoved, (removedNode) => {
      if (removedNode?.id !== undefined) {
        const rid = String(removedNode.id);
        const before = table.rows.length;
        table.rows = table.rows.filter((r) => String(r.nodeId) !== rid);
        if (table.rows.length !== before) table._serialise();
      }
      table._rebuildRows();
    });
  },
});

// ---queuePrompt hook ---─
// injects live values right before prompt submission.

const _originalQueuePrompt = app.queuePrompt.bind(app);

app.queuePrompt = async function (number, batchCount) {
  for (const node of (app.graph._nodes || [])) {
    if (node.comfyClass !== "ComfyNodeLedger") continue;
    const table = _activeTables.get(node);
    if (!table) continue;
    try {
      table.hiddenWidget.value = JSON.stringify(table.buildLivePayload());
    } catch (err) {
      console.warn("[ComfyNodeLedger] Failed to build live payload:", err);
    }
  }

  const result = await _originalQueuePrompt(number, batchCount);

  for (const node of (app.graph._nodes || [])) {
    if (node.comfyClass !== "ComfyNodeLedger") continue;
    const table = _activeTables.get(node);
    if (!table) continue;
    table._serialise();
  }

  return result;
};
