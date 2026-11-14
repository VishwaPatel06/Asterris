import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import charts, theme, viewer3d
from components.context import sidebar
from config import palette as P
from config.planetary_constants import PLANETS
from scientific_engine import dem
from scientific_engine.validation import load_or_run
from config.mission_presets import PRESETS
from simulations import drilling, physics, rover

ctx = sidebar("engineering")
theme.header("Mission Engineering", "Terramechanics, gravity offload, traverse planning and drilling estimates, with a verification report for every model.", "Workspace 05", "engineering")
t = ctx["target"]; g_t = PLANETS[t["body"]]["gravity"]
tab_r, tab_t, tab_d, tab_a = st.tabs(["Rover and gravity offload", "Traverse planner", "Drilling", "Model accuracy"])

with tab_r:
    a, b = st.columns([1, 2.2])
    with a:
        soil = physics.SOILS[st.selectbox("Soil model", list(physics.SOILS))]
        mass = st.number_input("Rover mass (kg)", 20.0, 2000.0, 150.0, 10.0); n_w = st.slider("Wheels", 2, 8, 4, 2)
        r_w = st.number_input("Wheel radius (m)", 0.05, 0.6, 0.20, 0.01); b_w = st.number_input("Wheel width (m)", 0.03, 0.4, 0.12, 0.01)
        slope = st.slider("Slope (deg)", 0, 35, 10); g = st.number_input(f"Target gravity (m/s2), {t['body']}", 0.5, 12.0, float(g_t), 0.01)
        eff = st.slider("Offload rig efficiency", 0.0, 1.0, 1.0, 0.05, help="Share of the excess weight the rig actually removes.")
        st.caption(f"Soil parameters: {soil.status}")
    with b:
        o = physics.gravity_offload(mass, n_w, r_w, b_w, g, slope, soil, eff)
        m = st.columns(4)
        m[0].metric("Offload force", f"{o['offload_force_N']:.0f} N", f"= {o['offload_mass_equiv_kg']:.1f} kg equivalent")
        m[1].metric("Residual gravity error", f"{o['residual_gravity_error_pct']:.1f}%")
        m[2].metric("Sinkage target / Earth", f"{o['sinkage_target_mm']:.1f} / {o['sinkage_earth_mm']:.1f} mm")
        m[3].metric("Max slope target / Earth", f"{o['max_slope_target_deg']:.0f} / {o['max_slope_earth_deg']:.0f} deg")
        ct, ce = o["climb_target"], o["climb_earth"]
        st.dataframe(pd.DataFrame([
            {"Quantity": "Normal load N = m g cos(slope)", "Earth": f"{o['normal_load_earth_N']:.0f} N", "Target gravity": f"{o['normal_load_target_N']:.0f} N", "Earth with rig": f"{o['normal_load_with_rig_N']:.0f} N"},
            {"Quantity": "Wheel sinkage", "Earth": f"{o['sinkage_earth_mm']:.1f} mm", "Target gravity": f"{o['sinkage_target_mm']:.1f} mm", "Earth with rig": f"{o['sinkage_rig_mm']:.1f} mm"},
            {"Quantity": "Slip needed to hold slope", "Earth": f"{ce['slip']:.2f}" if ce["feasible"] else ce["note"], "Target gravity": f"{ct['slip']:.2f}" if ct["feasible"] else ct["note"], "Earth with rig": "-"},
            {"Quantity": "Torque per wheel T = F r (N m)", "Earth": f"{o['torque_per_wheel_earth_Nm']:.1f}", "Target gravity": f"{o['torque_per_wheel_target_Nm']:.1f}", "Earth with rig": "-"},
            {"Quantity": "Energy per metre (J/m)", "Earth": f"{ce.get('energy_J_per_m', float('nan')):.0f}", "Target gravity": f"{ct.get('energy_J_per_m', float('nan')):.0f}", "Earth with rig": "-"}]),
            hide_index=True, width="stretch")
        ga = np.linspace(1.0, 10.0, 40); sw = physics.gravity_sweep(soil, mass, n_w, r_w, b_w, slope, ga)
        f1 = go.Figure(go.Scatter(x=sw["g"], y=sw["sinkage_mm"], line=dict(color=P.LAND[3], width=3), name="sinkage"))
        for nm, gv in (("Moon", 1.62), ("Mars", 3.72), ("Earth", 9.80665)):
            s_ = physics.gravity_sweep(soil, mass, n_w, r_w, b_w, slope, [gv])["sinkage_mm"][0]
            f1.add_trace(go.Scatter(x=[gv], y=[s_], mode="markers+text", text=[nm], textposition="top center", marker=dict(size=11, color=P.BODY_COLOR[nm]), showlegend=False))
        f1.update_layout(title="Wheel sinkage vs gravity (same vehicle and soil)", xaxis_title="gravity (m/s2)", yaxis_title="sinkage (mm)")
        c1, c2 = st.columns(2)
        c1.plotly_chart(charts.base(f1, 340, False), width="stretch")
        f2 = go.Figure()
        for nm, gv, col in (("Earth", physics.G_EARTH, P.BODY_COLOR["Earth"]), (t["body"], g, P.BODY_COLOR[t["body"]])):
            fw = physics.wheel_forces(soil, mass * gv * np.cos(np.radians(slope)) / n_w, r_w, b_w, physics.SLIP_GRID)
            f2.add_trace(go.Scatter(x=physics.SLIP_GRID, y=fw["DP_N"] * n_w, name=nm, line=dict(color=col, width=3)))
        f2.add_hline(y=mass * g * np.sin(np.radians(slope)), line=dict(color=P.MODERATE, dash="dot"), annotation_text="required pull on target")
        f2.update_layout(title="Total drawbar pull vs slip", xaxis_title="slip", yaxis_title="pull (N)")
        c2.plotly_chart(charts.base(f2, 340), width="stretch")
        tr = physics.accelerate_on_slope(soil, mass, g, n_w, r_w, b_w, slope, wheel_speed_rad_s=2.0)
        f3 = go.Figure(go.Scatter(x=tr["t"], y=tr["v"], line=dict(color=P.COSMIC_CYAN, width=3)))
        f3.update_layout(title="Transient speed, constant wheel speed 2 rad/s (RK4)", xaxis_title="time (s)", yaxis_title="speed (m/s)")
        st.plotly_chart(charts.base(f3, 280, False), width="stretch")
    theme.note("Bekker-Wong rigid-wheel model: flat soil, no grousers, no suspension compliance, constant slip along the arc, soil parameters independent of gravity (real regolith strength also depends on overburden). "
               "Verified against analytic solutions (see Model accuracy) but not validated against hardware or soil-bin data. Use for planning comparisons, not design sign-off.")

with tab_t:
    cands = ctx["cand_list"]; cid = st.selectbox("Earth candidate (terrain model)", [c["id"] for c in cands], format_func=lambda i: ctx["cands"][i]["name"].split(" (")[0], key="trc")
    c = ctx["cands"][cid]
    h, cell = dem.synthetic_dem(c["morphology"], 96, 2000.0, max(c["relief_m"] or 100, 50.0), c["roughness"] or 0.3)
    st.caption(f"Terrain: schematic {c['morphology']} surface scaled to the site's recorded relief (not surveyed). Upload a DEM in Data sources for real terrain.")
    s = dem.slope_deg(h, cell)
    p = st.columns(5)
    sr, sc_ = p[0].slider("Start row", 0, 95, 8), p[1].slider("Start col", 0, 95, 8); gr, gc = p[2].slider("Goal row", 0, 95, 88), p[3].slider("Goal col", 0, 95, 88)
    maxs = p[4].slider("Max slope (deg)", 5, 35, 20)
    w1 = st.columns(4); use_wp = w1[0].checkbox("Waypoint"); wr, wc = w1[1].slider("Waypoint row", 0, 95, 48), w1[2].slider("Waypoint col", 0, 95, 48)
    pts = [(sr, sc_)] + ([(wr, wc)] if use_wp else []) + [(gr, gc)]; path = []
    for a_, b_ in zip(pts[:-1], pts[1:]):
        seg = rover.astar(s, cell, a_, b_, maxs)
        if seg is None:
            path = None; break
        path += seg if not path else seg[1:]
    if path is None:
        st.error("No path under the slope limit. Increase the limit or move the points.")
    else:
        soil = physics.SOILS[list(physics.SOILS)[2]]
        crr = physics.rolling_resistance_coeff(soil, 150, g_t, 4, 0.2, 0.12)
        stt = rover.path_stats(h, cell, path, 150.0, g_t, crr)
        cov = rover.comms_coverage(h, cell, path, (sr, sc_))
        m = st.columns(5); m[0].metric("Distance", f"{stt['distance_m']:.0f} m"); m[1].metric("Elevation gain", f"{stt['elevation_gain_m']:.0f} m"); m[2].metric("Energy", f"{stt['energy_Wh']:.1f} Wh")
        m[3].metric("Resistance coeff.", f"{crr:.2f}", "from terramechanics"); m[4].metric("Line of sight to start", f"{cov:.0%}")
        mk = [{"label": "start", "lat": 0, "lon": 0, "color": P.CELESTIAL_MINT, "cell": [sr, sc_]}, {"label": "goal", "lat": 0, "lon": 0, "color": P.VOLCANIC[3], "cell": [gr, gc]}]
        viewer3d.show(viewer3d.explorer_html("Moon", 0, 0, "Traverse over schematic terrain", mk, grid=viewer3d.grid_payload(h, cell, True, "schematic"), start="terrain", exag=2.0, path=[list(q) for q in path[::2]]), 520)
        st.caption("Energy uses the target gravity and a soil resistance coefficient from the terramechanics model on the illustrative basaltic soil; no regeneration; 50% drivetrain efficiency assumed. Line of sight is geometric (no curvature or diffraction).")

with tab_d:
    a, b = st.columns(2)
    with a:
        medium = st.selectbox("Medium", list(drilling.MEDIA)); depth = st.number_input("Depth (m)", 0.1, 50.0, 1.0, 0.1); dia = st.number_input("Hole diameter (m)", 0.01, 0.5, 0.05, 0.01)
        rop = st.number_input("Rate of penetration (m/h)", 0.01, 20.0, 0.5, 0.05); lo, hi = drilling.MEDIA[medium]
        se = st.slider("Specific energy (MJ/m3)", float(lo), float(hi), float((lo + hi) / 2)); eff = st.slider("System efficiency", 0.05, 0.9, 0.25, 0.05)
        ice = st.slider("Ice mass fraction in cuttings", 0.0, 1.0, 0.0, 0.05); dT = st.number_input("Warming of ice (K)", 0.0, 200.0, 50.0, 5.0); sub = st.checkbox("Include sublimation (thermal management bound)")
    with b:
        e = drilling.drilling_estimate(depth, dia, rop, medium, se, eff)
        th = drilling.cryogenic_thermal_energy_wh(depth, dia, ice, dT, sub)
        m = st.columns(2); m[0].metric("Mechanical energy", f"{e['energy_Wh']:.1f} Wh"); m[1].metric("Mean power", f"{e['mean_power_W']:.0f} W")
        m = st.columns(2); m[0].metric("Duration", f"{e['duration_h']:.1f} h"); m[1].metric("Ice thermal energy", f"{th:.1f} Wh")
        st.caption(f"Range for this medium across the placeholder specific-energy band: {e['range_Wh'][0]:.1f} to {e['range_Wh'][1]:.1f} Wh.")
        st.markdown("**Teale specific energy from drill telemetry**")
        w_ = st.columns(3); wob = w_[0].number_input("Weight on bit (N)", 1.0, 5000.0, 200.0); tq = w_[1].number_input("Torque (N m)", 0.1, 500.0, 5.0); rpm = w_[2].number_input("RPM", 5.0, 2000.0, 120.0)
        te = drilling.teale_specific_energy(wob, tq, rpm, rop, dia)
        st.metric("Specific energy SE = F/A + 2 pi N T / (A u)", f"{te['specific_energy_MJ_m3']:.0f} MJ/m3", f"rotary power {te['rotary_power_W']:.0f} W")
    theme.note("Specific-energy bands are illustrative planning ranges, not calibrated to a specific drill or ice-cemented simulant. Thermal energy is an upper-bound style estimate that ignores heat shed to the ground. Conceptual, not a validated hardware prediction.")

with tab_a:
    from config.settings import get_settings
    from scientific_engine import validation_data as VD
    st.markdown("**Verification** checks that the code solves its equations correctly. **Validation** checks the equations against reality, which needs measured data. "
                "Everything that can be measured now is computed below; for the rest, upload your data and the same metrics are calculated on it.")
    force = st.button("Run all checks", type="primary")
    have = get_settings().cache_dir.joinpath("verification.json").exists()
    if force:
        with st.spinner("Running verification suite (about 40 seconds)..."):
            v = load_or_run(force=True)
    else:
        v = load_or_run() if have else None
    if v is None:
        st.info("Not run yet. Press Run all checks; results are cached afterwards.")
    else:
        st.caption(f"Model version {v['model_version']}, generated {v['generated_utc']}")
        sim_rows = v["similarity"]; fr = v["detector"]["rows"][0]; lit = (v.get("similarity_extended") or {}).get("literature") or {}
        m = st.columns(4)
        m[0].metric("Physics checks passed", f"{v['physics_passed']} / {v['physics_total']}")
        m[1].metric("Similarity checks passed", f"{sum(r['passed'] for r in sim_rows)} / {len(sim_rows)}")
        m[2].metric("Detector F1 (synthetic, fresh)", f"{fr['f1']:.2f}", f"P {fr['precision']:.2f} / R {fr['recall']:.2f}")
        m[3].metric("Physics throughput", f"{v['throughput']['evals_per_second']:,.0f} /s")
        tp, ts, td = st.tabs(["Physics engine", "Similarity ranking", "Landform detector"])

        # ------------------------------------------------------------------ physics
        with tp:
            df = pd.DataFrame(v["physics"])[["check", "metric", "value", "threshold", "passed", "what it checks"]]
            df["passed"] = df["passed"].map({True: "pass", False: "FAIL"})
            st.dataframe(df.style.format({"value": "{:.3g}", "threshold": "{:.3g}"}), hide_index=True, width="stretch")
            pe = v.get("physics_extended")
            if pe:
                c1, c2, c3 = st.columns(3)
                c1.metric("Agreement with Bekker closed form", f"{pe['closed_form']['mean_pct']:.1f}% mean", f"max {pe['closed_form']['max_pct']:.1f}% over {pe['closed_form']['cases']} cases")
                c2.metric("Shear-strength bound violations", f"{pe['strength_bound']['violations']} / {pe['strength_bound']['points']}")
                last = pe["convergence"][[r["arc points"] for r in pe["convergence"]].index(pe["operating_arc_points"])]
                c3.metric("Numerical error at operating resolution", f"{max(last['load error %'], last['pull error %']):.3f}%", f"{pe['operating_arc_points']} arc points")
                st.caption(pe["closed_form"]["note"])
                st.markdown("**Numerical convergence** (error versus a 1025-point reference)")
                st.dataframe(pd.DataFrame(pe["convergence"]).style.format({c_: "{:.4f}" for c_ in ["load error %", "pull error %", "torque error %"]}), hide_index=True, width="stretch")
                st.markdown("**Prediction uncertainty from soil-parameter uncertainty** (150 kg, 4 wheels; strength parameters +/-20%, friction angle +/-3 deg, n +/-0.1; 150 draws)")
                un = pd.DataFrame([{"Body": b, "Sinkage mean (mm)": u["sinkage_mm_mean"], "Sinkage 5-95% (mm)": f"{u['sinkage_p5_p95'][0]:.1f} to {u['sinkage_p5_p95'][1]:.1f}", "Sinkage CV (%)": u["sinkage_cv_pct"],
                                   "Pull at 20% slip (N)": u["pull_N_mean"], "Pull CV (%)": u["pull_cv_pct"]} for b, u in pe["uncertainty"].items()])
                st.dataframe(un.style.format({"Sinkage mean (mm)": "{:.1f}", "Sinkage CV (%)": "{:.0f}", "Pull at 20% slip (N)": "{:.1f}", "Pull CV (%)": "{:.0f}"}), hide_index=True, width="stretch")
                st.caption("This is how far predictions move if the soil parameters are only known to these tolerances. It measures sensitivity to inputs, not agreement with hardware.")
            st.markdown("#### Validate against your hardware or soil-bin data")
            st.caption("Upload wheel-test measurements. The engine predicts each test and reports RMSE, MAE, MAPE, bias and R2; optionally it calibrates the soil parameters to your data.")
            u1, u2 = st.columns([2, 1])
            vsoil = physics.SOILS[u1.selectbox("Soil model to test", list(physics.SOILS), key="vsoil")]
            u2.download_button("CSV template", VD.physics_template(), "physics_validation_template.csv", "text/csv", width="stretch")
            up = st.file_uploader("Measurements (CSV: wheel_load_N, slip, wheel_radius_m, wheel_width_m and any of drawbar_pull_N, sinkage_mm, torque_Nm)", type=["csv"], key="vphys")
            if up is not None:
                try:
                    mdf = pd.read_csv(up)
                except Exception as e:
                    mdf = None
                    st.error(f"Could not read the file: {e}")
                if mdf is not None:
                    ev = VD.evaluate_physics(mdf, vsoil)
                    if not ev["ok"]:
                        st.error(ev["error"])
                    else:
                        st.dataframe(pd.DataFrame(ev["metrics"]).T.style.format("{:.3g}"), width="stretch")
                        if st.button("Calibrate soil parameters to this data"):
                            cal = VD.calibrate_soil(mdf, vsoil)
                            if not cal["ok"]:
                                st.error(cal["error"])
                            else:
                                st.markdown("Before calibration"); st.dataframe(pd.DataFrame(cal["before"]).T.style.format("{:.3g}"), width="stretch")
                                st.markdown("After calibration"); st.dataframe(pd.DataFrame(cal["after"]).T.style.format("{:.3g}"), width="stretch")
                                st.json(cal["params"]); st.caption(cal["note"])

        # ------------------------------------------------------------------ similarity
        with ts:
            df = pd.DataFrame(sim_rows)[["check", "metric", "value", "threshold", "passed", "what it checks"]]
            df["passed"] = df["passed"].map({True: "pass", False: "FAIL"})
            st.dataframe(df.style.format({"value": "{:.3g}", "threshold": "{:.3g}"}), hide_index=True, width="stretch")
            se = v.get("similarity_extended") or {}
            if lit:
                st.markdown("**Agreement with published analogue pairings** (weak labels)")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Hit@3", f"{lit['hit_at_3']:.2f}", f"chance {lit['random_hit_at_3_expected']:.2f}"); c2.metric("Mean reciprocal rank", f"{lit['mean_reciprocal_rank']:.2f}")
                c3.metric("Mean average precision", f"{lit['map']:.2f}"); c4.metric("AUC", f"{lit['auc']:.2f}", "0.5 = chance")
                st.dataframe(pd.DataFrame(se["literature_per_target"]).style.format({"precision@3": "{:.2f}", "average precision": "{:.2f}", "reciprocal rank": "{:.2f}"}), hide_index=True, width="stretch")
                theme.note(f"Labels are analogue uses documented in the literature (for example Rio Tinto and Atacama for Mars, Hawaiian tubes for lava-tube work), compiled for this project; verify citations before publishing. "
                           f"They are not a ground truth of the best analogue, and the site values scored here are demonstration estimates, so this measures the engine on demonstration inputs. Objective used: {lit['objective']}.")
            if se.get("ablation_tau"):
                abl = se["ablation_tau"]
                fig = go.Figure(go.Bar(y=[d.replace("_", "/").title() for d in abl], x=list(abl.values()), orientation="h", marker_color=P.COSMIC_CYAN, text=[f"{x:.2f}" for x in abl.values()], textposition="outside"))
                fig.update_layout(title="Ranking dependence on each dimension (rank correlation when that dimension is removed; lower = more influential)", xaxis=dict(range=[0, 1.1]), yaxis=dict(autorange="reversed"))
                st.plotly_chart(charts.base(fig, 360, False), width="stretch")
            st.markdown("#### Score against your own labelled analogue pairs")
            cat = ctx["catalog"]
            pairs_t = pd.DataFrame([{"target_id": cat["targets"][0]["id"], "candidate_id": cat["candidates"][0]["id"], "relevance": 1}]).to_csv(index=False)
            l1, l2 = st.columns([2, 1])
            obj_v = l1.selectbox("Objective used for ranking", list(PRESETS), index=list(PRESETS).index("Geological Exploration") if "Geological Exploration" in PRESETS else 0, key="vobj")
            l2.download_button("CSV template", pairs_t, "analogue_labels_template.csv", "text/csv", width="stretch")
            upl = st.file_uploader("Labelled pairs (CSV: target_id, candidate_id, relevance 0/1 or graded)", type=["csv"], key="vlab")
            if upl is not None:
                try:
                    pdf = pd.read_csv(upl)
                except Exception as e:
                    pdf = None
                    st.error(f"Could not read the file: {e}")
                if pdf is not None:
                    prs, err = VD.parse_pairs(pdf)
                    if err:
                        st.error(err)
                    else:
                        ev = VD.evaluate_ranking(prs, cat["targets"], ctx["cand_list"], obj_v)
                        if not ev["ok"]:
                            st.error(ev["error"])
                        else:
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Hit@3", f"{ev['hit_at_3']:.2f}", f"chance {ev['random_hit_at_3_expected']:.2f}"); c2.metric("MRR", f"{ev['mean_reciprocal_rank']:.2f}")
                            c3.metric("AUC", f"{ev['auc']:.2f}"); c4.metric("Spearman", "n/a" if ev["spearman"] != ev["spearman"] else f"{ev['spearman']:.2f}")
                            st.dataframe(ev["per_target"].style.format({"precision@3": "{:.2f}", "average precision": "{:.2f}", "reciprocal rank": "{:.2f}"}), hide_index=True, width="stretch")

        # ------------------------------------------------------------------ detector
        with td:
            det = pd.DataFrame(v["detector"]["rows"])
            st.dataframe(det.style.format({c_: "{:.2f}" for c_ in ["precision", "recall", "f1", "false_positives_per_scene", "center_error_px"]}), hide_index=True, width="stretch")
            st.caption(v["detector"]["note"])
            rb = v.get("detector_robustness")
            if rb:
                st.markdown("**Robustness** (F1 on synthetic scenes)")
                st.dataframe(pd.DataFrame(rb["rows"]).style.format({"f1": "{:.2f}"}), hide_index=True, width="stretch")
            st.markdown("#### Real-terrain spot check on known impact craters")
            st.caption("Runs the detector on real elevation tiles around Meteor Crater, Lonar and Tenoumer and checks whether each known crater is found. Needs internet.")
            if st.button("Run real-terrain check"):
                with st.spinner("Fetching elevation tiles and scanning..."):
                    sc = VD.real_crater_spot_check()
                st.session_state["spot"] = sc
            sc = st.session_state.get("spot")
            if sc:
                st.dataframe(pd.DataFrame(sc["rows"]).astype(str), hide_index=True, width="stretch")
                if sc["n_checked"]:
                    st.metric("Recall on known craters", f"{sc['recall']:.0%}", f"{sc['n_checked']} sites checked")
                else:
                    st.warning("No elevation tiles could be fetched, so nothing was measured.")
                st.caption(sc["note"])
            st.markdown("#### Score discoveries against your own landform inventory")
            dr = st.session_state.get("disc_result")
            if not dr:
                st.caption("Run a discovery in Analog Discovery Lab first; its detections are then scored here.")
            else:
                inv_t = pd.DataFrame([{"lat": 35.0275, "lon": -111.0225, "diameter_m": 1186}]).to_csv(index=False)
                k1, k2 = st.columns([2, 1]); tol = k1.slider("Match tolerance (fraction of inventory diameter)", 0.2, 1.0, 0.5, 0.05)
                k2.download_button("CSV template", inv_t, "inventory_template.csv", "text/csv", width="stretch")
                ui = st.file_uploader("Inventory (CSV: lat, lon, diameter_m)", type=["csv"], key="vinv")
                if ui is not None:
                    try:
                        idf = pd.read_csv(ui)
                    except Exception as e:
                        idf = None
                        st.error(f"Could not read the file: {e}")
                    if idf is not None:
                        ev = VD.evaluate_inventory(dr["res"]["candidates"] + dr["res"]["rejected"], idf, ("crater",), tol)
                        if not ev["ok"]:
                            st.error(ev["error"])
                        else:
                            c1, c2, c3, c4 = st.columns(4)
                            c1.metric("Precision", f"{ev['precision']:.2f}"); c2.metric("Recall", f"{ev['recall']:.2f}"); c3.metric("F1", f"{ev['f1']:.2f}")
                            c4.metric("Position error", "n/a" if ev["mean_position_error_m"] != ev["mean_position_error_m"] else f"{ev['mean_position_error_m']:.0f} m")
                            st.caption(f"Diameter bias {ev['diameter_bias_pct']:.0f}%. {ev['note']}")
