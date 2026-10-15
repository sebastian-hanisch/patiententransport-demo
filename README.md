# Patiententransport: welche Zuweisungsregel hält den Notfall im Soll? – Streamlit-Demo

**[→ Demo live ausprobieren](https://sebastianhanisch-patiententransport-demo.streamlit.app/)**

Fall-Demo für die Website „Sebastian Hanisch – Operations Research und Machine Learning“ (`demos.html`). Ein synthetischer
Krankenhaustag (06:00 bis 18:00): Stationen, Notaufnahme und Diagnostik melden **Transportaufträge laufend**, eine Leitstelle
weist jedem einen freien Träger zu. Sechs Zuweisungsregeln fahren dieselben Meldungen, mit Prioritätsklassen, Bett- und
Rollstuhlfahrten, Bett-Qualifikation, gestaffelten Pausen und **Rückholungen, die erst nach der Untersuchung gemeldet werden**.
Eine exakte Schranke bei voller Kenntnis (CP-SAT) zeigt, was die Unkenntnis kostet.

Kernmodell: dynamisches Pickup-and-Delivery mit Prioritätsklassen und Soll-Zeiten, online, jeder Auftrag wird bedient
(Dial-a-Ride-Familie). Abgrenzung im Portfolio: `nahverkehr-demo` (Annahme/Ablehnung und Morgenplan), `servicegrad-tag-demo`
(Personalbemessung), `ems_demo` (Standortwahl). Hier geht es um die laufende Zuweisung einzelner Aufträge.

## Warum dieses Problem

Im Krankenhausalltag ist die Zuweisung selten das Problem, solange genug Träger da sind. Die Frage ist, **ab welcher Last
die Regel entscheidet**, ob ein Notfall genauso lange wartet wie Routine, und was eine Regel überhaupt leisten kann, wenn die
Kapazität nicht reicht. Kernfrage der Demo: *Wie viel macht die Zuweisungsregel aus?*

## Modell

- **Haus:** 14 Orte in drei Gebäuden (sechs Stationen auf sechs Etagen, Radiologie, MRT, Labor, Dialyse, OP, Notaufnahme,
  Aufnahme, Ausgang). Wegzeit = Weg / Tempo (leer 85, Rollstuhl 75, Bett 60, gehend 50 m/min) + Aufzug bei Etagenwechsel +
  1,5 min bei Gebäudewechsel, aufgerundet; Übergabe 2 min je Ende.
- **Aufträge:** Poisson je Minute mit Stundenprofil (OP-Beginn, Entlassungswelle). 55 % Hinfahrt zur Diagnostik mit Rückholung,
  10 % Notaufnahme, 5 % Verlegung, 15 % Entlassung, 15 % Aufnahme. Klassen Notfall / dringend / Routine (bei den Hinfahrten 2 / 26 / 72 %) mit Soll 10 / 20 / 40 min
  bis zur Ankunft am Abholort. Transportart Bett / Rollstuhl / gehend; Bett nur für qualifizierte Träger.
- **Rückholung:** die Meldung entsteht erst nach der Fahrt plus Untersuchung (15 bis 180 min im Mittel je Ziel).
- **Träger:** Anzahl, Anteil mit Bett-Qualifikation, Pausen ab 11:30 Uhr in vier Gruppen, 30 min.
- **Regeln (online):** FIFO, Nächster Auftrag, Priorität, Frist (EDD), Sammelfenster (Ungarisch im Takt, Notfall sofort),
  Vorausschau (Ungarisch jede Minute, bald freie Träger zählen mit, Notfall sofort). Formeln im 📐-Expander der App.
- **Schranke:** CP-SAT bei voller Kenntnis aller Aufträge und Untersuchungsdauern, ohne Vorwegbewegen; Zielgröße Σ Gewicht ·
  Wartezeit mit Gewichten 8 / 3 / 1.

## Methodik

Alle Regeln laufen auf **denselben Meldungen** (gleicher Seed). Ereignisgesteuerte Simulation in ganzen Minuten; wo eine Regel mit
der Zeit anders entscheidet (Vorausschau, Sammelfenster), läuft sie minutenweise bzw. im Takt. Befunde sind der **Median über
8 feste Tage** (`SWEEP_SEEDS`), nie ein einzelner Tag. Gezählt werden alle Hinfahrten, die vor 18:00 gemeldet wurden, samt ihren
Rückholungen, damit jede Regel dieselben Aufträge zählt.

## Befunde (gemessen, keine Behauptungen)

8 Träger, 85 % mit Bett-Qualifikation, mit Pausen, Sammelfenster 5 min; Median über 8 feste Tage; Tests in `tests/test_claims.py`.

| Frage | Befund |
|---|---|
| Entscheidet die Regel bei niedriger Last? | **Nein.** Bei 12 neuen Aufträgen je Stunde (Auslastung 47 %) liegen alle Regeln bei allen Klassen zwischen 2,8 und 5,1 min, keine Klasse verfehlt das Soll (`test_quiet_day_all_rules_are_equal`). |
| Wo kippt FIFO? | Bei 16 je Stunde (67 %) wartet ein Notfall 7,5 min (8 % verfehlen das Soll), bei **20 je Stunde (86 %) 24,7 min, 76 % verfehlen**, so lange wie Routine (24,5 min) (`test_fifo_tips_between_70_and_85_percent`). |
| Löst Priorität das? | Sie verschiebt die Last: Notfall 6,4 min, Routine aber **32,0 min** statt 24,5 min, 32 % der Routineaufträge verfehlen das Soll (`test_priority_moves_the_load_to_routine`). |
| Was leistet die Vorausschau? | Alle Klassen nahe am Soll: Notfall 5,9, dringend 7,4, Routine 9,1 min. Sie fährt weniger leer (29 % statt 39 % der Fahrminuten), die Auslastung bei denselben Aufträgen sinkt von 86 auf 78 % (`test_lookahead_keeps_all_classes_near_the_soll_by_saving_empty_trips`). |
| Hilft ein Sammelfenster? | **Nein, es schadet:** Routine 41,2 min (53 % verfehlt), dringend 18,1 min; Träger stehen bis zum Takt, Auslastung 76 % (`test_batching_window_hurts`). |
| Ist „immer der nächste Auftrag“ gut? | Für Routine ja (7,7 min bei 20 je Stunde), für den Notfall **gefährlich**: bei 24 je Stunde wartet er 130,1 min (FIFO 85,3), weil weit entfernte Orte immer zurückstehen, während Routine 20,4 min wartet (FIFO 83,0) (`test_nearest_order_starves_the_emergency_under_load`). |
| Was passiert an der Kapazitätsgrenze? | Bei 28 je Stunde (90 %) hält keine Regel das Soll: Vorausschau lässt Routine 92,7 min warten, 80 % verfehlen (`test_no_rule_holds_the_soll_at_the_capacity_limit`). Die Regel erzeugt keine Kapazität. |
| Gilt das mit mehr Trägern? | Ja, bei gleicher Auslastung: 12 Träger bei 30 je Stunde (88 %): FIFO-Notfall 31,0 min, Priorität-Routine 40,2 min, Vorausschau-Routine 9,4 min (`test_the_pattern_holds_with_twelve_porters_at_the_same_utilization`). |

### Hindsight-Schranke (Preis der Unkenntnis)

Kleine Spitzeninstanzen mit 3 Trägern (Ebenen „locker“ 60 min m 0,15, „mittel“ 60 min m 0,225, „dicht“ 40 min m 0,30; je 12 feste
Seeds), CP-SAT bis 20 s; `tests/test_claims.py::test_hindsight_price_of_ignorance_on_the_provable_instances`.

| Frage | Befund |
|---|---|
| Was lässt sich beweisen? | Von 36 Instanzen haben 23 höchstens 16 Fahrten (im Mittel 11,3) und sind **bewiesen optimal**; alle 13 mit mehr als 16 Fahrten bleiben in 20 s unbewiesen. Für einen ganzen Tag gibt es keine Schranke. |
| Wie weit liegen die Regeln vom Optimum? | Auf den 23 bewiesenen Instanzen (Summe der gewichteten Wartezeit gegen Summe des Optimums): FIFO 1,19, Nächster Auftrag 1,13, Priorität 1,16, Frist 1,16, Vorausschau 1,12, **Sammelfenster 1,58**. |
| Wie oft erreicht eine Regel das Optimum? | FIFO, Nächster Auftrag, Priorität und Frist in je 2 von 23, Vorausschau in 3, das Sammelfenster in 0. Keine Regel liegt je unter dem Optimum. |
| Was heißt das? | Die Unkenntnis kostet 12 bis 19 % gewichtete Wartezeit, mehr als die Wahl unter den vernünftigen Regeln (1,12 bis 1,19) ausmacht; nur das Sammelfenster fällt heraus. |

Diese Aussage gilt für Instanzen bis 16 Fahrten (eher niedrige bis mittlere Last in kurzem Ausschnitt). Bei höherer Last und längeren
Ausschnitten liefert der Löser nur eine untere Schranke; die Vorab-Messreihe (`transport-planung/messreihe_dispatch/ERGEBNIS.md`,
nicht Teil dieses Repos) zeigt dort die Vorausschau am nächsten an der Schranke, aber ohne Beweis.


## Ehrliche Grenzen

- **Synthetisches Haus.** Orte, Wegzeiten, Auftragsmix, Klassenanteile (Hinfahrten: Notfall 2 %, dringend 26 %, Routine 72 %) und Soll-Zeiten
  sind Annahmen; das ist keine Messung aus einem echten Betrieb. Die Befunde zeigen Mechanismen, keine Prognose für ein Haus.
- **Wenige Notfälle.** Auf den acht festen Tagen fallen 2 bis 9 an (Mittel 5,4 je Tag, 238 Hinfahrten); Tageswerte streuen stark, deshalb steht der Median über feste Tage.
- **Keine Notfall-Reserve.** Auch bei niedriger Last verfehlt ein Notfall das Soll gelegentlich (kein Träger in der Nähe frei);
  eine bewusst freigehaltene Reserve ist nicht modelliert.
- **Gleiche Gewichte für Wartezeit und Alterung** (8 / 3 / 1) sind eine Modellwahl, keine Messung.
- **Schranke nur klein.** Bis etwa 16 Fahrten beweist CP-SAT das Optimum meist, ab etwa 25 praktisch nie in 20 s; für den ganzen
  Tag (200 bis 450 Fahrten) gibt es keine Schranke. Ohne Beweis zeigt die App die untere Schranke und nennt das so.
- **Keine Empfehlung für den Betrieb.** Die Regeln sind Rechenverfahren im Modell, keine Handlungsanweisung.

## Befunde und Korrekturen gegenüber dem Plan

- Präfix `ptd_` statt `pt_` (`pt_` gehört `parallel-tempering-demo`).
- Die Vorab-Messreihe hatte die Priorität der Rückholungen von der Regel abhängig gemacht (Zähler der Rückholungen); im Demo-Kern ist
  sie je Auftrag fest. Die Zahlen verschieben sich leicht, das Muster nicht.
- **Gleichstände in der Zuordnung** sind im Kern deterministisch (fester, höchstens 1e-6 großer Aufschlag je Auftrag und Träger),
  damit das Ergebnis nicht von der scipy-Version abhängt. Ein erster, separabler Aufschlag trennte Vertauschungen nicht; der
  Orakel-Test gegen die minutengetaktete Referenz hat das gefunden.
- In der Vorausschau sind Träger, die gerade einen Notfall übernehmen, keine Kandidaten mehr für die optimale Zuordnung (die
  Vorab-Messreihe ließ sie mitzählen und verwarf dann das Paar).
- Neu gegenüber dem Plan: der Befund zu „Nächster Auftrag“ (Notfall verhungert), gefunden erst im Sweep des Demo-Kerns.

## Tests

83 Tests, rund 1 bis 2 Minuten (Windows, `_venvs/test`):

- **Regeln und Simulation (Einheiten):** je Regel an einem Mini-Haus mit drei Orten von Hand gerechnet (nächster Träger, Bett-Qualifikation,
  Reihenfolge von FIFO / Priorität / Frist, Sammelfenster nur im Takt, Vorausschau hält einen Auftrag für einen bald freien Träger),
  Simulation an Handrechnungen (eine Fahrt, Warten auf den einzigen Träger, Rückholung nach Untersuchung, Pause, Bett wartet auf den
  Qualifizierten, abgeschnittene Aufträge), Erhaltungssätze auf echten Tagen (jeder Auftrag genau einmal, kein Träger doppelt belegt).
- **Orakel:** die Ereignissimulation gegen eine minutengetaktete Referenz mit eigenen, naiven Regelschleifen (je Regel auf 12 Tagen, je
  Auftrag Wartezeit und Träger); Ungarisch-Zuordnung gegen Aufzählung; CP-SAT-Schranke gegen vollständige Aufzählung aller Zuordnungen
  und Reihenfolgen (bis 5 Fahrten, 2 Träger); unabhängiger Zeitplan-Prüfer erkennt verletzte Zeitpläne; keine Online-Regel schlägt das
  bewiesene Optimum.
- **Claims:** jede Zahl der Befundtabellen (`tests/test_claims.py`), inklusive der Hindsight-Zahlen auf den 23 beweisbaren Instanzen.
- **Eckfälle:** jeder Regler am Minimum und Maximum, alle Minima und alle Maxima zusammen, Worst-Case (4 Träger bei 36 Aufträgen je Stunde,
  die Simulation endet an der Obergrenze), keine Aufträge, Ergebnis unabhängig von `PYTHONHASHSEED`.
- **Mutationslauf** (`tools/oracle_mutation.py` im Website-Repo, 60 Mutanten aus den Kernmodulen): 8 Überlebende, einzeln gelesen. Zwei
  echte Lücken geschlossen: der Zeitplan-Prüfer war an der Stelle `max(Meldung, frei)` nicht festgenagelt, und die Zahl der Bett-
  Qualifizierten rundete mit Pythons Banker-Rundung (4,5 wurde 4; jetzt ganzzahlig ab .5 aufgerundet, mit Grenztests). Sechs
  äquivalente Mutanten sind in `tests/mutation_state.json` festgehalten.
- **Oberfläche:** AppTest-Rauchtest (jeder Button, jeder Regler an den Grenzen), Presets, Permalink-Begrenzung, PDF für jedes Preset, Footer,
  Laufzeit-Importe gegen `requirements.txt`.


## Dateistruktur

| Datei | Zweck |
|---|---|
| `.github/workflows/tests.yml` | CI: Push, Pull Request, wöchentlicher Canary |
| `.gitignore` | venv, Caches, Streamlit-Secrets |
| `.streamlit/config.toml` | Streamlit-Einstellungen (keine Nutzungsstatistik) |
| `app.py` | Streamlit-App |
| `ptd_constants.py` | Regler-Grenzen, feste Annahmen, Klassen, Regeln, Farben, Presets |
| `ptd_hospital.py` | das synthetische Haus, Wegzeiten je Transportart |
| `ptd_orders.py` | Meldungen über den Tag, Rückholung |
| `ptd_dispatch.py` | die sechs Zuweisungsregeln als reine Funktionen |
| `ptd_simulation.py` | ereignisgesteuerte Simulation eines Tages |
| `ptd_hindsight.py` | CP-SAT-Schranke bei voller Kenntnis, unabhängiger Prüfer |
| `ptd_evaluation.py` | Kennzahlen, Verdikte, Dichte-Sweep |
| `ptd_presets.py` | Permalink (Begrenzen), Presets, Zufalls-Seed-Button |
| `ptd_visualization.py` | Plotly-Abbildungen (Achsen gesperrt) |
| `ptd_pdf_export.py` | PDF-Bericht des aktuellen Tages (fpdf2) |
| `requirements.txt` | Laufzeit-Bibliotheken (ungepinnt) |
| `requirements-dev.txt` | Laufzeit plus pytest |
| `tests/` | Einheiten, Orakel, Claims, Eckfälle, AppTest, Footer, Laufzeit-Importe; `reference_sim.py` ist die Referenz des Orakels |

## Bewusst nicht umgesetzt

- **Notfall-Reserve** (bewusst freigehaltene Träger), **Mehrfachtransporte** (zwei Patienten gleichzeitig),
  **Aufzugskapazität als Warteschlange**, **Vorhersage der Rückholung**. Jede davon würde eine eigene Frage aufmachen.
- **Hellseher mit Vorpositionierung** als Schranke: die Schranke hier kennt die Zukunft, bewegt Träger aber erst nach der Meldung.

## Lokal ausführen

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

Streamlit Community Cloud: Python 3.12 einstellen, `ortools` kommt aus `requirements.txt`.

## Tests ausführen

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Gebaut mit Streamlit, Plotly, NumPy, SciPy, OR-Tools und fpdf2.

---

Diese Demo ist Teil des Portfolios von [Sebastian Hanisch](https://sebastianhanisch.net) – Operations Research und Machine Learning ([Über mich](https://sebastianhanisch.net/ueber-mich.html)). Mehr zum Thema: [Tourenplanung optimieren](https://sebastianhanisch.net/tourenplanung-optimierung.html).
