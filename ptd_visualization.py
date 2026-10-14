"""Plotly-Abbildungen. Alle Achsen sind gesperrt (fixedrange), damit Touch-Geräte beim Scrollen nicht am Diagramm hängen bleiben."""

import plotly.graph_objects as go

import ptd_constants as C


def lock_axes(fig):
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def _base(fig, height=380, bottom=10):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=bottom), legend=dict(orientation="h", y=-0.22),
                      plot_bgcolor="rgba(0,0,0,0)")
    return lock_axes(fig)


def clock_label(minute: int) -> str:
    h = C.DAY_START_HOUR + minute // 60
    return f"{h:02d}:{minute % 60:02d}"


def build_wait_bars(stats: dict):
    """Mittlere Wartezeit je Regel, je Klasse ein Balken; gestrichelt das Soll der Klasse."""
    names = [C.RULE_NAME[r] for r in C.RULES]
    fig = go.Figure()
    for c, label in enumerate(C.CLASS_NAMES):
        fig.add_trace(go.Bar(x=names, y=[stats[r].classes[c].mean for r in C.RULES], name=label, marker_color=C.COLOR_CLASS[c],
                             hovertemplate="%{x}: %{y:.1f} min<extra>" + label + "</extra>"))
    for c, label in enumerate(C.CLASS_NAMES):
        fig.add_hline(y=C.SOLL[c], line_dash="dot", line_color=C.COLOR_CLASS[c], opacity=0.7,
                      annotation_text=f"Soll {label} {C.SOLL[c]} min", annotation_position="top right")
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="mittlere Wartezeit bis zur Ankunft des Trägers (min)", rangemode="tozero")
    return _base(fig, bottom=40)


def build_queue(queues: dict, rules=("fifo", "prio", "voraus")):
    """Wartende Aufträge über den Tag (Raster 5 min)."""
    fig = go.Figure()
    for r in rules:
        q = queues[r]
        xs = [clock_label(5 * i) for i in range(len(q))]
        fig.add_trace(go.Scatter(x=xs, y=list(q), mode="lines", name=C.RULE_NAME[r], line=dict(color=C.COLOR_RULE[r], width=2.5),
                                 hovertemplate="%{x}: %{y} wartend<extra>" + C.RULE_NAME[r] + "</extra>"))
    fig.update_xaxes(title_text="Uhrzeit", tickmode="array", tickvals=[clock_label(m) for m in range(0, C.DAY_MINUTES + 1, 120)])
    fig.update_yaxes(title_text="wartende Aufträge", rangemode="tozero")
    return _base(fig, bottom=40)


def build_rate_sweep(rows: list[dict], cls: int, rules=C.RULES):
    """Mittlere Wartezeit einer Klasse über die Auftragsdichte (Median der festen Tage); gestrichelt das Soll."""
    xs = [r["rate"] for r in rows]
    fig = go.Figure()
    for rule in rules:
        fig.add_trace(go.Scatter(x=xs, y=[r[rule]["wait"][cls] for r in rows], mode="lines+markers", name=C.RULE_NAME[rule],
                                 line=dict(color=C.COLOR_RULE[rule], width=2.5),
                                 hovertemplate="%{x} je Stunde: %{y:.1f} min<extra>" + C.RULE_NAME[rule] + "</extra>"))
    fig.add_hline(y=C.SOLL[cls], line_dash="dot", line_color=C.COLOR_SOLL, annotation_text=f"Soll {C.SOLL[cls]} min",
                  annotation_position="top left")
    fig.update_xaxes(title_text="neue Aufträge je Stunde (Mittel)", tickmode="array", tickvals=xs)
    fig.update_yaxes(title_text=f"mittlere Wartezeit {C.CLASS_NAMES[cls]} (min)", rangemode="tozero")
    return _base(fig, bottom=40)


def build_hospital_map(h):
    """Schema des Hauses: waagerecht die Lage (m), senkrecht die Etage; Farbe = Gebäude."""
    palette = {0: "#2F6B65", 1: "#4C78A8", 2: "#D98A1F"}
    names = {0: "Haupthaus", 1: "Bettenhaus", 2: "Ambulanztrakt"}
    fig = go.Figure()
    for b in sorted(set(h.building)):
        idx = [i for i in range(len(h.names)) if h.building[i] == b]
        fig.add_trace(go.Scatter(x=[h.x[i] for i in idx], y=[h.floor[i] for i in idx], mode="markers+text", name=names[b],
                                 text=[h.names[i] for i in idx], textposition="top center", marker=dict(size=13, color=palette[b]),
                                 hovertemplate="%{text}<extra>" + names[b] + "</extra>"))
    fig.update_xaxes(title_text="Lage im Haus (m)")
    fig.update_yaxes(title_text="Etage", dtick=1, range=[-2, 8.5])
    return _base(fig, height=420, bottom=40)


def build_hindsight_bars(res, online: dict):
    """Gewichtete Wartezeit je Regel im Verhältnis zur unteren Schranke (1,0 = Schranke); der Balken des Optimums, wenn bewiesen."""
    bound = res.bound if res.bound else res.objective
    labels = [C.RULE_NAME[r] for r in C.RULES]
    values = [online[r] / bound if bound else 0 for r in C.RULES]
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=[C.COLOR_RULE[r] for r in C.RULES],
                           hovertemplate="%{x}: %{y:.2f} x Schranke<extra></extra>"))
    fig.add_hline(y=1.0, line_dash="dot", line_color=C.COLOR_SOLL, annotation_text="Hindsight-Schranke", annotation_position="top left")
    fig.update_yaxes(title_text="gewichtete Wartezeit / Schranke", rangemode="tozero")
    return _base(fig, height=320, bottom=30)
