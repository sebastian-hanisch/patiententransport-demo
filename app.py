"""Patiententransport: welche Zuweisungsregel hält den Notfall im Soll? - interaktive Fall-Demo
Sebastian Hanisch - Operations Research und Machine Learning

Ein synthetischer Krankenhaustag (06:00 bis 18:00): Transportaufträge treffen online ein, Träger fahren sie nach einer Zuweisungsregel.
Sechs Regeln laufen auf denselben Meldungen; eine Schranke bei voller Kenntnis (CP-SAT) zeigt, was Unkenntnis kostet.

Lauffähig mit: streamlit run app.py
"""

import streamlit as st

import ptd_constants as C
import ptd_hindsight as HS
from ptd_evaluation import Settings, analyse, fmt, pct, sweep_rate, verdict_core, verdict_sweep
from ptd_hospital import HOSPITAL
from ptd_pdf_export import build_pdf
from ptd_presets import (
    apply_preset,
    bounds,
    init_session_state_defaults,
    load_permalink_settings,
    randomize_seed,
    sync_query_params,
)
from ptd_simulation import n_qualified_from_percent, qualified_flags
from ptd_visualization import build_hindsight_bars, build_hospital_map, build_queue, build_rate_sweep, build_wait_bars

st.set_page_config(page_title="Patiententransport – Sebastian Hanisch", layout="wide")


@st.cache_data(show_spinner=False)
def _analysis(settings):
    return analyse(settings)


@st.cache_data(show_spinner=False)
def _sweep(base):
    return sweep_rate(base)


@st.cache_data(show_spinner=False)
def _hindsight(level, seed, qual, batch):
    orders = HS.make_instance(HOSPITAL, level, seed)
    res, online, jobs = HS.compare_rules(HOSPITAL, orders, C.HINDSIGHT_PORTERS, qual, C.HINDSIGHT_TIME_LIMIT, batch)
    nq = n_qualified_from_percent(C.HINDSIGHT_PORTERS, qual)
    problems = HS.verify_schedule(HOSPITAL, jobs, res, qualified_flags(C.HINDSIGHT_PORTERS, nq)) if res.objective is not None else []
    return res, online, problems


st.title("🏥 Patiententransport: welche Zuweisungsregel hält den Notfall im Soll?")
st.markdown(
    """
Im Krankenhaus melden Stationen, Notaufnahme und Diagnostik Transportaufträge **laufend und unvorhersehbar**; eine Leitstelle weist
jedem einen freien Träger zu. Diese Demo fährt einen **synthetischen Krankenhaustag** mit **sechs Zuweisungsregeln** auf denselben
Meldungen, mit **Prioritätsklassen**, **Bett- und Rollstuhlfahrten** und **Rückholungen, die erst nach der Untersuchung gemeldet werden**.
Die Frage ist, ab welcher Last die Regel entscheidet, ob ein Notfall so lange wartet wie Routine.

Weiter unten: die **Kernfrage**, ein **Experiment** über die Auftragsdichte und der Expander **🔧 Wie wir das erreichen – vollständiger
Methodenvergleich** mit den Regeln, dem Haus und der **🧮 exakten Schranke bei voller Kenntnis**.
"""
)

st.caption("🎯 Schnellstart – ein Beispielszenario laden:")
cols = st.columns(len(C.PRESETS))
for col, name in zip(cols, C.PRESETS):
    with col:
        st.button(name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP.get(name, ""), key=f"preset_{name}")

st.caption("🔗 Die Adresszeile oben spiegelt Ihre aktuelle Konfiguration wider – einfach kopieren, um ein Szenario zu teilen.")

load_permalink_settings()
init_session_state_defaults()

with st.sidebar:
    st.header("⚙️ Einstellungen")
    st.markdown("**Aufträge und Personal**")
    rate = st.slider("Neue Aufträge je Stunde (Mittel)", *bounds("rate_slider"), key="rate_slider",
                     help="Mittlere Zahl neuer Hinfahrten je Stunde; der Tag hat Spitzen (OP-Beginn, Entlassungen). Rückholungen kommen hinzu.")
    porters = st.slider("Träger im Dienst", *bounds("porters_slider"), key="porters_slider", help="Alle Träger beginnen an der Aufnahme.")
    qual = st.slider("Träger mit Bett-Qualifikation [%]", *bounds("qual_slider"), key="qual_slider",
                     help="Nur diese Träger dürfen Betten fahren; mindestens einer.")
    st.markdown("**Betrieb**")
    breaks = st.radio("Pausen", C.BREAKS_OPTIONS, key="breaks_radio", help="Gestaffelt ab 11:30 Uhr, je Träger 30 Minuten.")
    batch = st.slider("Sammelfenster [min]", *bounds("batch_slider"), key="batch_slider",
                      help="Takt der Regel „Sammelfenster“: nicht dringende Aufträge werden nur alle so viele Minuten zugeordnet.")
    st.markdown("**Zufall**")
    seed = st.number_input("Zufalls-Seed des Tages", *bounds("seed_input"), key="seed_input", step=1)
    st.button("🎲 Neuen Tag generieren", width="stretch", on_click=randomize_seed)

sync_query_params({"rate_slider": int(rate), "porters_slider": int(porters), "qual_slider": int(qual), "batch_slider": int(batch),
                   "breaks_radio": breaks, "seed_input": int(seed)})

settings = Settings(int(rate), int(porters), int(qual), int(batch), breaks, int(seed))
a = _analysis(settings)
fifo, voraus = a.stats["fifo"], a.stats["voraus"]

# --- Ergebnis ------------------------------------------------------------------------------------------------------------------------------

st.markdown("## 🎯 Ergebnis")
st.caption(f"Ein Tag, {a.n_orders} Hinfahrten im Meldefenster 06:00 bis 18:00 plus ihre Rückholungen; alle Regeln fahren dieselben Meldungen. "
           f"Auslastung der Träger unter FIFO: {pct(fifo.utilization)}, unter Vorausschau: {pct(voraus.utilization)}.")
n_notfall = fifo.classes[0].n
m1, m2, m3 = st.columns(3)
# Delta immer als „mein Wert minus Referenz“; die Farbe regelt delta_color="inverse" (Vorzeichen-Falle, DEMO-PLAYBOOK §2).
m1.metric("Notfall wartet (Vorausschau)", f"{fmt(voraus.classes[0].mean)} min",
          delta=f"{voraus.classes[0].mean - fifo.classes[0].mean:+.1f} min gegen FIFO".replace(".", ","), delta_color="inverse")
m2.metric("Routine wartet (Vorausschau)", f"{fmt(voraus.classes[2].mean)} min",
          delta=f"{voraus.classes[2].mean - fifo.classes[2].mean:+.1f} min gegen FIFO".replace(".", ","), delta_color="inverse")
m3.metric("Leerfahrten (Vorausschau)", pct(voraus.empty_share),
          delta=f"{100 * (voraus.empty_share - fifo.empty_share):+.0f} Prozentpunkte gegen FIFO", delta_color="inverse")
if n_notfall < 5:
    st.caption(f"Hinweis: An diesem Tag gibt es nur {n_notfall} Notfälle; ihre Mittelwerte schwanken stark. "
               "Das Experiment unten mittelt über feste Tage.")
if not all(s.complete for s in a.stats.values()):
    st.warning("Bei dieser Last werden nicht alle Aufträge bis zur Zeitobergrenze der Simulation erledigt; offene Aufträge zählen mit der Wartezeit bis dahin, die Werte sind untere Grenzen.")

st.plotly_chart(build_wait_bars(a.stats), width="stretch", key="chart_wait")
st.caption("Mittlere Wartezeit von der Meldung bis zur Ankunft des Trägers am Abholort, je Regel und Klasse. Gestrichelt: das Soll der Klasse.")
st.plotly_chart(build_queue(a.queues), width="stretch", key="chart_queue")
st.caption("Wartende Aufträge über den Tag unter FIFO, Priorität und Vorausschau.")

kind_core, text_core = verdict_core(a)

if st.button("📄 PDF erstellen", key="pdf_make"):
    st.session_state["pdf_bytes"] = (settings, build_pdf(a, text_core))
if "pdf_bytes" in st.session_state and st.session_state["pdf_bytes"][0] == settings:
    st.download_button("⬇️ PDF herunterladen", data=st.session_state["pdf_bytes"][1], file_name="patiententransport.pdf",
                       mime="application/pdf", key="pdf_download")

# --- Kernfrage -----------------------------------------------------------------------------------------------------------------------------

st.markdown("## ❓ Kernfrage: Wie viel macht die Zuweisungsregel aus?")
getattr(st, kind_core)(text_core)

rows_table = []
for r in C.RULES:
    s = a.stats[r]
    rows_table.append({
        "Regel": C.RULE_NAME[r],
        "Notfall Mittel [min]": round(s.classes[0].mean, 1), "Notfall Soll verfehlt [%]": round(100 * s.classes[0].miss),
        "dringend Mittel [min]": round(s.classes[1].mean, 1), "dringend Soll verfehlt [%]": round(100 * s.classes[1].miss),
        "Routine Mittel [min]": round(s.classes[2].mean, 1), "Routine Soll verfehlt [%]": round(100 * s.classes[2].miss),
        "Auslastung [%]": round(100 * s.utilization), "Leerfahrten [%]": round(100 * s.empty_share),
    })
st.dataframe(rows_table, hide_index=True, width="stretch")

# --- Experiment: Dichte --------------------------------------------------------------------------------------------------------------------

st.subheader("🔬 Experiment: ab welcher Dichte laufen die Regeln auseinander?")
st.markdown(
    f"Derselbe Betrieb ({settings.porters} Träger, {settings.qual} % mit Bett-Qualifikation, {settings.breaks}), die Auftragsdichte von "
    f"{C.RATE_SWEEP[0]} bis {C.RATE_SWEEP[-1]} je Stunde, jede Zelle der **Median über {len(C.SWEEP_SEEDS)} feste Tage**. "
    "Das rechnet etwas länger und läuft erst auf Klick."
)
sweep_base = Settings(C.DEFAULT_RATE, settings.porters, settings.qual, settings.batch, settings.breaks, C.DEFAULT_SEED)
if st.button("Experiment rechnen", key="sweep_start"):
    st.session_state["sweep_done"] = sweep_base
if st.session_state.get("sweep_done") == sweep_base:
    with st.spinner("Rechne alle Regeln über alle Dichten und Tage ..."):
        rows = _sweep(sweep_base)
    kind_s, text_s = verdict_sweep(rows)
    getattr(st, kind_s)(text_s)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Notfall**")
        st.plotly_chart(build_rate_sweep(rows, 0), width="stretch", key="sweep_notfall")
    with c2:
        st.markdown("**Routine**")
        st.plotly_chart(build_rate_sweep(rows, 2), width="stretch", key="sweep_routine")
    st.caption("Auslastung unter FIFO je Dichte: " + ", ".join(f"{r['rate']} je Stunde: {pct(r['fifo']['util'])}" for r in rows) + ".")

st.markdown("---")

# --- Methodenvergleich ---------------------------------------------------------------------------------------------------------------------

with st.expander("🔧 Wie wir das erreichen – vollständiger Methodenvergleich"):
    tab_rules, tab_exact, tab_house = st.tabs(["Die sechs Regeln", "🧮 Exakt (OR-Tools)", "Das Haus"])
    with tab_rules:
        st.markdown("Jede Regel entscheidet nur mit dem, was bis jetzt bekannt ist: wartende Aufträge, freie Träger, deren Standort.")
        for r in C.RULES:
            st.markdown(f"**{C.RULE_NAME[r]}.** {C.RULE_TEXT[r]}")
        st.caption("Eine freie Qualifikation reicht nicht für Betten: Bett-Aufträge gehen nur an Träger mit Bett-Qualifikation. "
                   "Notfälle werden unter Sammelfenster und Vorausschau immer sofort dem nächsten passenden freien Träger zugewiesen.")
    with tab_exact:
        st.markdown(
            "Die **Hindsight-Schranke** beantwortet: Was wäre möglich, wenn die Leitstelle **alle Aufträge des Ausschnitts im Voraus kennte**? "
            f"Ein Träger darf trotzdem erst nach der Meldung losfahren. Gelöst wird auf kleinen Instanzen mit {C.HINDSIGHT_PORTERS} Trägern "
            "(CP-SAT, Zielgröße: Summe Klassengewicht mal Wartezeit mit Gewichten 8 / 3 / 1). Für den ganzen Tag gibt es keine Schranke: "
            "ab etwa 25 Aufträgen im Ausschnitt beweist der Löser das Optimum in der Zeitgrenze nicht mehr."
        )
        level = st.radio("Last des Ausschnitts", list(C.HINDSIGHT_LEVELS), key="hs_level", horizontal=True)
        hs_seed = st.number_input("Seed des Ausschnitts", 0, C.SEED_MAX, C.HINDSIGHT_SEEDS[0], key="hs_seed", step=1)
        orders_hs = HS.make_instance(HOSPITAL, level, int(hs_seed))
        n_jobs = len(HS.make_jobs(orders_hs))
        st.caption(f"Dieser Ausschnitt hat {n_jobs} Fahrten (Hin- und Rückfahrten).")
        key_hs = (level, int(hs_seed), settings.qual, settings.batch)
        if n_jobs > C.HINDSIGHT_MAX_JOBS:
            st.info(f"Mehr als {C.HINDSIGHT_MAX_JOBS} Fahrten: dafür rechnet die Demo keine Schranke. Anderen Seed oder lockerere Last wählen.")
        elif n_jobs == 0:
            st.info("In diesem Ausschnitt gibt es keinen Auftrag.")
        else:
            if st.button("Schranke berechnen", key="hs_start"):
                st.session_state["hs_done"] = key_hs
            if st.session_state.get("hs_done") == key_hs:
                with st.spinner(f"CP-SAT löst bis zu {int(C.HINDSIGHT_TIME_LIMIT)} s ..."):
                    res, online, problems = _hindsight(*key_hs)
                if res.objective is None:
                    st.error(f"Der Löser lieferte keine Lösung (Status {res.status}).")
                else:
                    if problems:
                        st.error("Der Prüfer fand Regelverletzungen im Zeitplan: " + "; ".join(problems))
                    if res.status == "OPTIMAL":
                        st.success(f"Optimum bewiesen: gewichtete Wartezeit {fmt(res.objective, 0)} bei {res.n_jobs} Fahrten.")
                        ref, ref_name = res.objective, "Optimum"
                    else:
                        st.warning(f"Zeitgrenze erreicht: beste gefundene Lösung {fmt(res.objective, 0)}, untere Schranke {fmt(res.bound, 0)}. "
                                   "Der Preis der Unkenntnis liegt höchstens im gezeigten Verhältnis zur Schranke.")
                        ref, ref_name = res.bound, "untere Schranke"
                    st.plotly_chart(build_hindsight_bars(res, online), width="stretch", key="chart_hs")
                    st.caption(f"Gewichtete Wartezeit je Online-Regel im Verhältnis zur {ref_name}: " +
                               ", ".join(f"{C.RULE_NAME[r]} {fmt(online[r] / ref, 2)}" for r in C.RULES) + ".")
    with tab_house:
        st.plotly_chart(build_hospital_map(HOSPITAL), width="stretch", key="chart_house")
        st.caption("Schema des synthetischen Hauses: 14 Orte in drei Gebäuden. Wegzeit = Weg / Tempo (leer 85, Rollstuhl 75, Bett 60, "
                   "gehend 50 m/min) plus Aufzug bei Etagenwechsel plus Zuschlag beim Gebäudewechsel; Übergabe 2 min je Ende.")

# --- Mathematische Formulierung --------------------------------------------------------------------------------------------------------

with st.expander("📐 Mathematische Formulierung"):
    st.markdown(
        r"""
**Aufträge.** Auftrag $j$ hat Meldezeit $r_j$, Abholort $o_j$, Zielort $d_j$, Klasse $c_j \in \{\text{Notfall}, \text{dringend}, \text{Routine}\}$
und Transportart $k_j$. Eine Hinfahrt zur Diagnostik erzeugt nach der Untersuchungsdauer $e_j$ eine Rückholung mit Meldezeit
$r_{j'} = s_j + 2h + \tau_{k}(o_j, d_j) + e_j$; sie ist vorher unbekannt.

**Wartezeit.** Fährt Träger $p$ von seinem Standort $x_p$ zu Auftrag $j$, kommt er zur Zeit $s_j = t + \lambda(x_p, o_j)$ an ($t \ge r_j$
der Zuweisungszeitpunkt, $\lambda$ die Leerfahrt-Wegzeit). Wartezeit $w_j = s_j - r_j$. Danach ist der Träger bis
$s_j + 2h + \tau_{k_j}(o_j, d_j)$ gebunden, $h = 2$ min Übergabe.

**Soll und Zielgröße.** Soll $\sigma_c = 10 / 20 / 40$ min. Verfehlquote $= \Pr(w_j > \sigma_{c_j})$. Zielgröße der Schranke
$\sum_j \omega_{c_j}\, w_j$ mit $\omega = (8, 3, 1)$.

**Online-Regeln.** FIFO sortiert nach $r_j$, Priorität nach $(c_j, r_j)$, Frist nach $r_j + \sigma_{c_j}$; jeder Auftrag nimmt den nächsten
passenden freien Träger. Nächster Auftrag wählt wiederholt das Paar mit kleinstem $\lambda$. Sammelfenster und Vorausschau lösen eine
Zuordnung mit Kosten $c_{pj} = \max(f_p - t, 0) + \lambda(x_p, o_j) - \omega_{c_j}(t - r_j)$ ($f_p$ Zeit, zu der $p$ frei wird); das
Sammelfenster nur über freie Träger und nur im Takt, die Vorausschau jede Minute und mit Trägern, die innerhalb von 8 min frei werden,
bestätigt werden aber nur Paare mit jetzt freiem Träger. Notfälle gehen vorher sofort an den nächsten passenden freien Träger.

**Hindsight-Schranke.** Alle $r_j$ und $e_j$ bekannt. Je Träger ein Kreis über Depot und Aufträge; für eine Folge $i \to j$ auf demselben
Träger gilt $s_j \ge s_i + 2h + \tau_{k_i}(o_i, d_i) + \lambda(d_i, o_j)$ und $s_j \ge r_j + \lambda(d_i, o_j)$; jeder Auftrag wird genau
einem Träger zugeordnet, Betten nur an qualifizierte. Minimiere $\sum_j \omega_{c_j}(s_j - r_j)$. Das ist NP-schwer; der Löser liefert
bei Zeitgrenze eine untere Schranke, kein Optimum.
"""
    )

# --- Grenzen -------------------------------------------------------------------------------------------------------------------------------

st.subheader("🚧 Wo die Annahmen enden")
st.markdown(
    """
- **Synthetisches Haus.** Orte, Wegzeiten, Auftragsmix, Klassenanteile und Soll-Zeiten sind Annahmen und keine Messung aus einem echten
  Betrieb; die Zahlen zeigen Mechanismen, keine Prognose für ein bestimmtes Haus.
- **Wenige Notfälle.** Je Tag fallen nur wenige Notfälle an, ihre Mittelwerte streuen stark; Befunde stehen deshalb als Median über
  feste Tage.
- **Keine Reserve.** Auch bei niedriger Last verfehlt ein Notfall das Soll gelegentlich, weil kein Träger in der Nähe frei ist. Eine
  bewusst freigehaltene Reserve ist nicht modelliert.
- **Schranke nur klein.** Die exakte Schranke gibt es nur für kurze Ausschnitte mit wenigen Trägern; ein Beweis für den ganzen Tag fehlt.
- **Keine Empfehlung für den Betrieb.** Die Regeln sind Rechenverfahren im Modell, keine Handlungsanweisung für ein Haus.
"""
)

st.markdown("---")
st.caption(
    "Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – "
    "Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). "
    "Mehr zum Thema: [Tourenplanung optimieren](https://sebastianhanisch.net/tourenplanung-optimierung.html)."
)
