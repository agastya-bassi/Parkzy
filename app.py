"""
ParkShare – Streamlit Demo
Run: streamlit run app.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

from pricing_engine import (
    ParkSharePricer,
    fetch_upcoming_events,
    homeowner_alerts,
    SURGE_FEATURES,
    LA_METER_RATES,
)

# ─── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ParkShare – Dynamic Pricing Demo",
    page_icon="🅿️",
    layout="wide",
)

# ─── init (cached) ────────────────────────────────────────────────────────────
@st.cache_resource
def get_pricer():
    p = ParkSharePricer(model_dir="/tmp/parkshare_models")
    with st.spinner("Warming up RL model with simulated history …"):
        p.simulate_rl_training(n=300)
    return p

pricer = get_pricer()

# ─── header ───────────────────────────────────────────────────────────────────
st.title("🅿️  Parkzy — Dynamic Pricing Engine")
st.caption("Airbnb for parking · Inglewood / USC area · ML-powered, self-improving")

tab_price, tab_events, tab_rl, tab_model = st.tabs(
    ["💰 Pricing", "🎤 Events & Alerts", "🤖 RL Learning", "📊 Model Insights"]
)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: PRICING SIMULATOR
# ══════════════════════════════════════════════════════════════════════════════
with tab_price:
    st.subheader("Live price calculator")

    col_in, col_out = st.columns([1, 1], gap="large")

    with col_in:
        zone          = st.selectbox("Zone", list(LA_METER_RATES.keys()), index=5)
        active_users  = st.slider("Active users on app right now", 5, 600, 80)
        listed_spots  = st.slider("Listed spots available", 1, 100, 25)
        hours_to_event = st.slider("Hours until nearest event (999 = none)", 0.0, 48.0, 4.0, step=0.5)
        event_size    = st.slider("Event size (0 = small / 1 = sold-out stadium)", 0.0, 1.0, 0.6, step=0.05)
        day_of_week   = st.selectbox("Day of week", ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"], index=5)
        hour          = st.slider("Hour of day (24 h)", 0, 23, 18)
        temperature   = st.slider("Temperature (°F)", 45, 105, 72)

        dow_int = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].index(day_of_week)

        if st.button("⚡ Calculate price", type="primary", use_container_width=True):
            result = pricer.price(
                zone           = zone,
                active_users   = active_users,
                listed_spots   = listed_spots,
                hours_to_event = hours_to_event if hours_to_event < 48 else 999,
                event_size     = event_size,
                day_of_week    = dow_int,
                hour           = hour,
                temperature    = temperature,
            )
            st.session_state["last_result"] = result

    with col_out:
        if "last_result" in st.session_state:
            r = st.session_state["last_result"]
            meter_rate = LA_METER_RATES.get(zone, LA_METER_RATES["default"])

            st.metric("🏷️ Recommended price / hr", f"${r['final_price']:.2f}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Base (anchor)", f"${r['base']:.2f}", help="LA meter avg × 0.85")
            c2.metric("Surge multiplier", f"{r['surge_mult']:.2f}×")
            c3.metric("RL adjustment", f"{r['rl_delta']:+.2f}×")

            st.divider()
            savings = meter_rate - r["final_price"]
            if savings > 0:
                st.success(f"✅ ${savings:.2f}/hr cheaper than a street meter — competitive edge maintained.")
            else:
                st.warning("⚠️ Price is at or above street meter rate due to very high demand.")

            st.markdown("**Demand snapshot**")
            demand_ratio = active_users / max(listed_spots, 1)
            st.progress(min(demand_ratio / 10, 1.0), text=f"Demand/supply ratio: {demand_ratio:.1f}×")

            # Simulate booking outcome for RL
            col_book, col_miss = st.columns(2)
            with col_book:
                if st.button("✅ Simulate: spot booked", use_container_width=True):
                    revenue = r["final_price"] * 2   # avg 2 hr session
                    pricer.record_outcome(booking_completed=True, revenue=revenue)
                    st.success(f"RL updated! +${revenue:.2f} reward signal recorded.")
            with col_miss:
                if st.button("❌ Simulate: no booking", use_container_width=True):
                    pricer.record_outcome(booking_completed=False, revenue=0)
                    st.info("RL updated. Vacancy penalty recorded — will nudge price down.")
        else:
            st.info("← Set parameters and hit **Calculate price**")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: EVENTS & HOMEOWNER ALERTS
# ══════════════════════════════════════════════════════════════════════════════
with tab_events:
    st.subheader("Upcoming events near Inglewood / USC")

    api_key = st.text_input(
        "Ticketmaster API key (optional — leave blank to use mock data)",
        type="password",
        placeholder="paste key here …",
    )

    if st.button("🔍 Fetch events", use_container_width=False):
        with st.spinner("Fetching…"):
            events = fetch_upcoming_events(api_key or None)
            st.session_state["events"] = events
            st.session_state["alerts"] = homeowner_alerts(events)

    if "events" in st.session_state:
        events = st.session_state["events"]
        alerts = st.session_state["alerts"]

        df_ev = pd.DataFrame(events)[["name","venue","hours_until","capacity","demand_score"]]
        df_ev.columns = ["Event", "Venue", "Hours until", "Capacity", "Demand score"]
        df_ev["Demand score"] = df_ev["Demand score"].apply(lambda x: f"{x:.2f}")
        st.dataframe(df_ev, use_container_width=True, hide_index=True)

        st.subheader("📱 Homeowner notification queue")
        if alerts:
            for a in alerts:
                level = a["alert_level"]
                icon  = "🔥" if level == "high" else "📍"
                color = "error" if level == "high" else "warning"
                getattr(st, color)(f"{icon} **{a['name']}** — {a['message']}")
        else:
            st.info("No events cross the alert threshold right now.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: RL POLICY VIEWER
# ══════════════════════════════════════════════════════════════════════════════
with tab_rl:
    st.subheader("RL Q-table — learned pricing adjustments")
    st.caption(
        "State = (demand bucket 0–4, event proximity 0–2). "
        "Action = delta applied on top of surge multiplier. "
        "Updated live as booking outcomes are recorded."
    )

    df_q = pricer.rl.policy_summary()
    if not df_q.empty:
        df_q["demand_bucket"] = df_q["state"].apply(lambda s: int(s.split("_")[0]))
        df_q["event_bucket"]  = df_q["state"].apply(lambda s: int(s.split("_")[1]))
        df_q["event_bucket"]  = df_q["event_bucket"].map({0: "No event", 1: "3-12 hrs", 2: "0-3 hrs"})
        df_q["demand_bucket"] = df_q["demand_bucket"].map(lambda x: f"Demand {x} ({x*2}–{x*2+2}× D/S)")
        pivot = df_q.pivot(index="demand_bucket", columns="event_bucket", values="best_delta")
        st.dataframe(
            pivot.style.background_gradient(cmap="RdYlGn", axis=None),
            use_container_width=True,
        )
    else:
        st.info("Q-table empty — simulate some bookings in the Pricing tab first.")

    st.divider()
    st.subheader("Pricing history this session")
    if pricer.history:
        df_h = pd.DataFrame(pricer.history)[
            ["timestamp","zone","base","surge_mult","rl_delta","final_price","demand_ratio"]
        ]
        df_h.columns = ["Time","Zone","Base","Surge×","RL Δ","Final $/hr","D/S ratio"]
        st.dataframe(df_h.tail(20)[::-1], use_container_width=True, hide_index=True)
    else:
        st.info("No pricing calls yet.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: MODEL INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
with tab_model:
    st.subheader("Surge model — feature importances")
    fi = pricer.surge_model.feature_importances()
    df_fi = pd.DataFrame({"Feature": list(fi.keys()), "Importance": list(fi.values())})
    df_fi = df_fi.sort_values("Importance", ascending=False)
    st.bar_chart(df_fi.set_index("Feature"), use_container_width=True)

    st.divider()
    st.subheader("Price sensitivity explorer")
    st.caption("Hold everything else constant, sweep one variable.")

    sweep_var = st.selectbox("Variable to sweep", ["active_users","listed_spots","hours_to_event","event_size"])
    sweep_range = {
        "active_users":    range(10, 510, 20),
        "listed_spots":    range(2, 80, 3),
        "hours_to_event":  [x/2 for x in range(0, 49)],
        "event_size":      [x/20 for x in range(0, 21)],
    }[sweep_var]

    defaults = dict(
        zone="inglewood", active_users=80, listed_spots=20,
        hours_to_event=4, event_size=0.6, day_of_week=5, hour=18, temperature=72,
    )

    rows = []
    for v in sweep_range:
        kw = {**defaults, sweep_var: v}
        r  = pricer.price(**kw)
        rows.append({sweep_var: v, "price": r["final_price"]})

    df_sw = pd.DataFrame(rows).set_index(sweep_var)
    st.line_chart(df_sw, use_container_width=True)

    st.divider()
    st.caption(
        "Model: GradientBoostingRegressor (200 trees, lr=0.05, depth=4). "
        "RL: Epsilon-greedy Q-table (ε=0.15, α=0.10, γ=0.90). "
        "Retrained on each batch of new booking outcomes."
    )
