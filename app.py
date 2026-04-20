import gradio as gr
import json
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io
from collections import Counter
from PIL import Image

# ─── Node-Farben nach Typ ──────────────────────────────────────────────────────
NODE_COLORS = {
    "n8n-nodes-base.manualTrigger": "#ff6b6b",
    "n8n-nodes-base.scheduleTrigger": "#ff8c00",
    "n8n-nodes-base.cron": "#ff8c00",
    "n8n-nodes-base.webhook": "#4ecdc4",
    "n8n-nodes-base.httpRequest": "#45b7d1",
    "n8n-nodes-base.set": "#96ceb4",
    "n8n-nodes-base.if": "#ffd166",
    "n8n-nodes-base.switch": "#c77dff",
    "n8n-nodes-base.code": "#06d6a0",
    "n8n-nodes-base.function": "#06d6a0",
    "n8n-nodes-base.functionItem": "#06d6a0",
    "n8n-nodes-base.slack": "#611f69",
    "n8n-nodes-base.gmail": "#ea4335",
    "n8n-nodes-base.googleSheets": "#0f9d58",
    "n8n-nodes-base.airtable": "#18bfff",
    "@n8n/n8n-nodes-langchain.openAi": "#412991",
    "n8n-nodes-base.openAi": "#412991",
    "n8n-nodes-base.telegram": "#2ca5e0",
    "n8n-nodes-base.emailSend": "#e07b39",
    "n8n-nodes-base.postgres": "#336791",
    "n8n-nodes-base.mysql": "#4479a1",
    "n8n-nodes-base.merge": "#f4a261",
    "n8n-nodes-base.splitInBatches": "#e9c46a",
    "n8n-nodes-base.wait": "#a8dadc",
    "n8n-nodes-base.noOp": "#adb5bd",
    "n8n-nodes-base.respondToWebhook": "#4ecdc4",
}
DEFAULT_COLOR = "#6c757d"


def node_color(node_type: str) -> str:
    return NODE_COLORS.get(node_type, DEFAULT_COLOR)


def node_label(node_type: str) -> str:
    """Kurzer Anzeigename aus vollem Typ-String (camelCase → Leerzeichen)."""
    name = node_type.split(".")[-1]
    result = ""
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            result += " "
        result += ch
    return result


# ─── Parsing ───────────────────────────────────────────────────────────────────

def parse_workflow(json_text: str):
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        return None, f"JSON-Fehler: {exc}"
    if "nodes" not in data:
        return None, "Kein gültiges n8n-Workflow JSON — 'nodes'-Feld fehlt."
    return data, None


# ─── Basis-Statistiken (Free) ──────────────────────────────────────────────────

def basic_stats(wf: dict) -> dict:
    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})

    conn_count = sum(
        len(target_list)
        for src_conns in connections.values()
        for output_lists in src_conns.values()
        for target_list in output_lists
    )

    type_counter = Counter(n.get("type", "unknown") for n in nodes)
    triggers = [
        n.get("name", n.get("type", ""))
        for n in nodes
        if "trigger" in n.get("type", "").lower() or "webhook" in n.get("type", "").lower()
    ]

    return {
        "name": wf.get("name", "Unbenannter Workflow"),
        "node_count": len(nodes),
        "conn_count": conn_count,
        "unique_types": len(type_counter),
        "triggers": triggers,
        "type_counter": type_counter,
    }


def stats_to_html(s: dict) -> str:
    trigger_text = ", ".join(s["triggers"]) if s["triggers"] else "Kein Trigger gefunden"

    rows = ""
    for ntype, count in sorted(s["type_counter"].items(), key=lambda x: -x[1]):
        color = node_color(ntype)
        label = node_label(ntype)
        rows += (
            f"<tr>"
            f"<td style='padding:6px 8px'>"
            f"<span style='background:{color};color:#fff;padding:2px 10px;"
            f"border-radius:20px;font-size:12px;font-weight:600'>{label}</span>"
            f"</td>"
            f"<td style='padding:6px 8px;text-align:right;font-weight:600'>{count}×</td>"
            f"</tr>"
        )

    return f"""
    <div style='font-family:Inter,system-ui,sans-serif'>
      <h3 style='margin:0 0 16px;color:#1a1a2e'>📊 Workflow: {s['name']}</h3>

      <div style='display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:24px'>
        <div style='background:#eff6ff;border-radius:10px;padding:16px;text-align:center'>
          <div style='font-size:32px;font-weight:800;color:#2563eb'>{s['node_count']}</div>
          <div style='font-size:12px;color:#64748b;margin-top:2px'>Nodes</div>
        </div>
        <div style='background:#f0fdf4;border-radius:10px;padding:16px;text-align:center'>
          <div style='font-size:32px;font-weight:800;color:#16a34a'>{s['conn_count']}</div>
          <div style='font-size:12px;color:#64748b;margin-top:2px'>Verbindungen</div>
        </div>
        <div style='background:#fff7ed;border-radius:10px;padding:16px;text-align:center'>
          <div style='font-size:32px;font-weight:800;color:#ea580c'>{s['unique_types']}</div>
          <div style='font-size:12px;color:#64748b;margin-top:2px'>Node-Typen</div>
        </div>
      </div>

      <p style='margin:0 0 16px'><strong>Trigger:</strong> {trigger_text}</p>

      <table style='width:100%;border-collapse:collapse'>
        <thead>
          <tr style='background:#f1f5f9'>
            <th style='padding:8px;text-align:left;font-size:13px'>Node-Typ</th>
            <th style='padding:8px;text-align:right;font-size:13px'>Anzahl</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """


# ─── Graph-Visualisierung (Premium) ───────────────────────────────────────────

def build_graph(wf: dict):
    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})

    G = nx.DiGraph()
    node_map = {n["name"]: n for n in nodes}

    for n in nodes:
        G.add_node(n["name"], node_type=n.get("type", "unknown"))

    for src, src_conns in connections.items():
        for _otype, output_lists in src_conns.items():
            for target_list in output_lists:
                for conn in target_list:
                    tgt = conn.get("node", "")
                    if tgt and tgt in node_map:
                        G.add_edge(src, tgt)

    return G, node_map


def visualize(wf: dict) -> Image.Image:
    G, node_map = build_graph(wf)

    fig, ax = plt.subplots(figsize=(13, 8), facecolor="#0d1117")
    ax.set_facecolor("#0d1117")

    if len(G.nodes()) == 0:
        ax.text(0.5, 0.5, "Keine Nodes gefunden",
                ha="center", va="center", color="white",
                fontsize=14, transform=ax.transAxes)
        ax.axis("off")
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#0d1117")
        buf.seek(0)
        plt.close(fig)
        return Image.open(buf)

    # Layout: hierarchisch wenn DAG, sonst Spring
    try:
        if nx.is_directed_acyclic_graph(G):
            layers = list(nx.topological_generations(G))
            pos = {}
            for y_idx, layer in enumerate(layers):
                layer = list(layer)
                for x_idx, node in enumerate(layer):
                    pos[node] = (x_idx - len(layer) / 2.0, -y_idx * 1.8)
        else:
            raise ValueError("not a DAG")
    except Exception:
        pos = nx.spring_layout(G, k=2.5, iterations=60, seed=42)

    # Edges
    if G.edges():
        nx.draw_networkx_edges(
            G, pos, ax=ax,
            edge_color="#58a6ff", arrows=True,
            arrowsize=18, width=1.8,
            connectionstyle="arc3,rad=0.05",
            min_source_margin=18, min_target_margin=18,
            alpha=0.85,
        )

    # Nodes
    for name in G.nodes():
        ndata = node_map.get(name, {})
        color = node_color(ndata.get("type", "unknown"))
        nx.draw_networkx_nodes(G, pos, nodelist=[name], ax=ax,
                               node_color=color, node_size=1100, alpha=0.95)

    # Labels
    labels = {n: (n[:13] + "…" if len(n) > 14 else n) for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=labels, ax=ax,
                            font_size=7, font_color="white", font_weight="bold")

    ax.set_title(
        f"🔀  {wf.get('name', 'Workflow')}",
        color="white", fontsize=13, pad=16, fontweight="bold",
    )
    ax.axis("off")
    plt.tight_layout(pad=1.5)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0d1117")
    buf.seek(0)
    plt.close(fig)
    return Image.open(buf)


# ─── Komplexitäts-Score (Premium) ─────────────────────────────────────────────

def complexity_score(wf: dict) -> tuple:
    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})

    conn_count = sum(
        len(tlist)
        for sc in connections.values()
        for ol in sc.values()
        for tlist in ol
    )

    score = min(len(nodes) * 4, 40) + min(conn_count * 3, 30)

    types = {n.get("type", "") for n in nodes}
    if any("code" in t or "function" in t for t in types):
        score += 10
    if any("if" in t or "switch" in t for t in types):
        score += 10
    if any("split" in t or "loop" in t for t in types):
        score += 10

    score = min(score, 100)

    if score < 30:
        level, color = "Einfach", "#16a34a"
    elif score < 60:
        level, color = "Mittel", "#d97706"
    else:
        level, color = "Komplex", "#dc2626"

    return score, level, color


def complexity_html(wf: dict) -> str:
    score, level, color = complexity_score(wf)
    bar_w = score * 2
    return f"""
    <div style='font-family:Inter,system-ui,sans-serif'>
      <h3 style='margin:0 0 20px'>📐 Komplexitäts-Score</h3>
      <div style='display:flex;align-items:center;gap:24px'>
        <div style='font-size:56px;font-weight:800;color:{color};line-height:1'>{score}</div>
        <div>
          <div style='font-size:20px;font-weight:700;color:{color}'>{level}</div>
          <div style='background:#e2e8f0;border-radius:8px;height:14px;width:200px;margin-top:10px;overflow:hidden'>
            <div style='background:{color};height:14px;width:{bar_w}px;border-radius:8px'></div>
          </div>
          <div style='font-size:12px;color:#64748b;margin-top:6px'>{score}/100 Punkte</div>
        </div>
      </div>
      <p style='margin-top:20px;color:#475569;font-size:14px'>
        Berechnet aus: Anzahl Nodes, Verbindungen, Code-Nodes, Bedingungen und Schleifen.
      </p>
    </div>
    """


# ─── Optimierungstipps (Premium) ──────────────────────────────────────────────

def optimization_tips(wf: dict) -> str:
    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})
    tips = []

    # Error Handling
    if not any("error" in n.get("type", "").lower() for n in nodes) and len(nodes) > 3:
        tips.append(("⚠️ Kein Error Handling",
                     "Füge einen Error-Trigger oder Try/Catch-Node hinzu — Produktions-Workflows brauchen Fehlerbehandlung."))

    # Zu groß für einen Workflow
    if len(nodes) > 20:
        tips.append(("📦 Workflow zu groß",
                     f"{len(nodes)} Nodes in einem Workflow erschwert die Wartung. Teile ihn in Sub-Workflows auf (Execute Workflow Node)."))

    # Viele HTTP Requests
    http_nodes = [n for n in nodes if "httpRequest" in n.get("type", "")]
    if len(http_nodes) >= 3:
        tips.append(("🌐 Viele HTTP Requests",
                     f"{len(http_nodes)} HTTP-Request-Nodes gefunden. Prüfe ob Batching oder parallele Ausführung möglich ist."))

    # Isolierte Nodes
    connected = set()
    for src, sc in connections.items():
        connected.add(src)
        for ol in sc.values():
            for tlist in ol:
                for c in tlist:
                    connected.add(c.get("node", ""))
    isolated = [n["name"] for n in nodes if n["name"] not in connected]
    if isolated:
        tips.append(("🔌 Isolierte Nodes",
                     f"Nicht verbundene Nodes: {', '.join(isolated[:4])}{' …' if len(isolated) > 4 else ''}. Prüfe ob diese noch benötigt werden."))

    # Viele Set-Nodes
    set_nodes = [n for n in nodes if n.get("type") == "n8n-nodes-base.set"]
    if len(set_nodes) >= 4:
        tips.append(("🔧 Viele Set-Nodes",
                     f"{len(set_nodes)} Set-Nodes könnten in einem Code-Node zusammengefasst werden — vereinfacht den Workflow."))

    # Kein Trigger
    triggers = [n for n in nodes
                if "trigger" in n.get("type", "").lower() or "webhook" in n.get("type", "").lower()]
    if not triggers:
        tips.append(("🚫 Kein Trigger",
                     "Kein Trigger-Node gefunden. Der Workflow kann nicht automatisch gestartet werden."))

    if not tips:
        tips.append(("✅ Gut strukturiert", "Keine offensichtlichen Optimierungspunkte gefunden. Sauber!"))

    items = "".join(
        f"<li style='margin-bottom:14px'>"
        f"<strong>{t}</strong><br>"
        f"<span style='color:#475569;font-size:14px'>{d}</span></li>"
        for t, d in tips
    )
    return f"""
    <div style='font-family:Inter,system-ui,sans-serif'>
      <h3 style='margin:0 0 16px'>🚀 Optimierungsempfehlungen</h3>
      <ul style='list-style:none;padding:0;margin:0'>{items}</ul>
    </div>
    """


# ─── Premium-Placeholder ───────────────────────────────────────────────────────

PREMIUM_LOCKED = """
<div style='text-align:center;padding:48px 24px;background:#f8fafc;
            border-radius:12px;border:2px dashed #cbd5e1;font-family:Inter,sans-serif'>
  <div style='font-size:40px;margin-bottom:12px'>🔒</div>
  <h3 style='margin:0 0 8px;color:#475569'>Premium Feature</h3>
  <p style='color:#64748b;margin:0 0 16px'>
    Dieses Feature ist ab dem <strong>Basic-Plan ($19/Mo)</strong> verfügbar.
  </p>
  <p style='color:#94a3b8;font-size:13px;margin:0'>
    API-Key eingeben oder auf
    <a href='https://noyra-x.de/kontakt' style='color:#2563eb'>noyra-x.de</a> upgraden.
  </p>
</div>
"""


# ─── Hauptfunktion ─────────────────────────────────────────────────────────────

def analyze(file, api_key: str):
    """Gradio callback → (stats_html, graph_img, tips_html, complexity_html)"""
    if file is None:
        msg = "<p style='color:#ef4444;font-family:Inter,sans-serif'>⚠️ Bitte zuerst eine JSON-Datei hochladen.</p>"
        return msg, None, PREMIUM_LOCKED, PREMIUM_LOCKED

    try:
        with open(file, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except Exception as exc:
        err = f"<p style='color:#ef4444'>Fehler beim Lesen: {exc}</p>"
        return err, None, PREMIUM_LOCKED, PREMIUM_LOCKED

    wf, error = parse_workflow(raw)
    if error:
        err_html = f"<p style='color:#ef4444;font-family:Inter,sans-serif'>❌ {error}</p>"
        return err_html, None, PREMIUM_LOCKED, PREMIUM_LOCKED

    stats_out = stats_to_html(basic_stats(wf))

    is_premium = bool(api_key and len(api_key.strip()) > 8)

    if is_premium:
        try:
            graph_img = visualize(wf)
        except Exception as exc:
            print(f"Visualisierungs-Fehler: {exc}")
            graph_img = None
        tips_out = optimization_tips(wf)
        complex_out = complexity_html(wf)
    else:
        graph_img = None
        tips_out = PREMIUM_LOCKED
        complex_out = PREMIUM_LOCKED

    return stats_out, graph_img, tips_out, complex_out


# ─── Gradio UI ────────────────────────────────────────────────────────────────

css = """
.gradio-container { max-width: 860px !important; }
.upload-hint { font-size: 13px; color: #64748b; margin-top: 6px; }
footer { display: none !important; }
"""

with gr.Blocks(
    title="n8n Workflow Visualizer | Noyra-X",
    theme=gr.themes.Soft(
        primary_hue=gr.themes.colors.blue,
        neutral_hue=gr.themes.colors.slate,
    ),
    css=css,
) as demo:

    gr.Markdown("""
# 🔀 n8n Workflow Visualizer
**Analysiere und visualisiere deine n8n-Workflows** — kostenlos, direkt im Browser.

Von [Noyra-X](https://noyra-x.de) — KI-Automatisierung für KMUs.
    """)

    with gr.Row():
        with gr.Column(scale=3):
            file_input = gr.File(
                label="n8n Workflow JSON",
                file_types=[".json"],
                type="filepath",
            )
            gr.Markdown(
                "*Workflow in n8n exportieren: Menü → Download*",
                elem_classes="upload-hint",
            )
        with gr.Column(scale=2):
            api_key_input = gr.Textbox(
                label="API-Key (optional, für Premium-Features)",
                placeholder="noyra-xxxx-xxxx-xxxx",
                type="password",
            )
            gr.Markdown(
                "Noch kein Key? [noyra-x.de/kontakt](https://noyra-x.de/kontakt)",
                elem_classes="upload-hint",
            )

    analyze_btn = gr.Button("🔍  Workflow analysieren", variant="primary", size="lg")

    gr.Markdown("---")

    with gr.Tabs():
        with gr.TabItem("📊 Basis-Statistiken  🟢 Kostenlos"):
            stats_out = gr.HTML()

        with gr.TabItem("🗺️ Graph-Visualisierung  🔵 Premium"):
            graph_out = gr.Image(label="Workflow-Graph", type="pil")

        with gr.TabItem("🚀 Optimierungstipps  🔵 Premium"):
            tips_out = gr.HTML()

        with gr.TabItem("📐 Komplexitäts-Score  🔵 Premium"):
            complex_out = gr.HTML()

    analyze_btn.click(
        fn=analyze,
        inputs=[file_input, api_key_input],
        outputs=[stats_out, graph_out, tips_out, complex_out],
    )

    gr.Markdown("""
---
🤖 Entwickelt von **[Noyra-X](https://noyra-x.de)** — Wir bauen KI-Agentensysteme für Unternehmen.
📧 [kontakt@noyra-x.de](mailto:kontakt@noyra-x.de) · [Alle Tools entdecken](https://noyra-x.de)
    """)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
