"""
Parkzy – Streamlit Presentation App
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
    LA_METER_RATES,
    base_price,
)

# ─── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Parkzy",
    page_icon="🅿️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* cleaner font and background */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1100px; }

    /* metric cards */
    [data-testid="metric-container"] {
        background: #f8f9fb;
        border: 1px solid #e8eaed;
        border-radius: 12px;
        padding: 1rem 1.2rem;
    }
    [data-testid="metric-container"] label { color: #666; font-size: 0.8rem; }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 1.6rem; font-weight: 700; color: #1a1a2e;
    }

    /* big price display */
    .big-price {
        font-size: 3.5rem; font-weight: 800; color: #2563eb;
        line-height: 1.1; margin: 0.5rem 0;
    }
    .price-label { font-size: 0.9rem; color: #888; margin-bottom: 0.2rem; }

    /* section cards */
    .card {
        background: white; border: 1px solid #e8eaed;
        border-radius: 16px; padding: 1.5rem; margin-bottom: 1rem;
        color: #1a1a2e;
    }
    .card h4 { color: #1a1a2e; margin-bottom: 0.5rem; }
    .card p, .card li { color: #374151; }
    .card strong { color: #1a1a2e; }
    .card ul { padding-left: 1.2rem; }
    .notif-high strong, .notif-high span { color: #1a1a2e; }
    .notif-med strong, .notif-med span { color: #1a1a2e; }

    /* pill badges */
    .badge-green { background:#dcfce7; color:#166534; padding:3px 10px; border-radius:20px; font-size:0.78rem; font-weight:600; }
    .badge-orange { background:#fff7ed; color:#9a3412; padding:3px 10px; border-radius:20px; font-size:0.78rem; font-weight:600; }
    .badge-blue { background:#eff6ff; color:#1d4ed8; padding:3px 10px; border-radius:20px; font-size:0.78rem; font-weight:600; }

    /* tab styling */
    button[data-baseweb="tab"] { font-size: 0.9rem; font-weight: 500; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #2563eb; }

    /* notification cards */
    .notif-high { background:#fff1f0; border-left:4px solid #ef4444; border-radius:8px; padding:1rem; margin:0.5rem 0; }
    .notif-med  { background:#fffbeb; border-left:4px solid #f59e0b; border-radius:8px; padding:1rem; margin:0.5rem 0; }

    /* hide streamlit branding */
    #MainMenu, footer { visibility: hidden; }

    /* mode toggle */
    .mode-box { background:#f1f5f9; border-radius:12px; padding:1rem 1.2rem; margin-bottom:1rem; }
</style>
""", unsafe_allow_html=True)

# ─── init ─────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_pricer():
    p = ParkSharePricer(model_dir="/tmp/parkzy_models")
    p.simulate_rl_training(n=300)
    return p

pricer = get_pricer()

# ─── header ───────────────────────────────────────────────────────────────────
col_logo, col_tagline = st.columns([1, 3])
with col_logo:
    st.markdown("## 🅿️ Parkzy")
with col_tagline:
    st.markdown("<p style='padding-top:0.6rem; color:#888; font-size:0.95rem;'>Airbnb for parking · Inglewood & USC · Powered by ML</p>", unsafe_allow_html=True)

st.divider()

# ─── tabs ─────────────────────────────────────────────────────────────────────
tab_home, tab_homeowner, tab_events, tab_how = st.tabs([
    "🏠  Overview",
    "🚗  Homeowner Portal",
    "🎤  Events & Alerts",
    "🧠  How the AI Works",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW — live market snapshot
# ══════════════════════════════════════════════════════════════════════════════
with tab_home:
    st.markdown("### Live market snapshot")
    st.caption("What drivers are seeing right now across the Inglewood / USC area")

    # top KPI row
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Active drivers searching", "247", "+18 last hour")
    k2.metric("Spots listed today", "34")
    k3.metric("Avg price / hr", "$4.20", "+$0.80 vs yesterday")
    k4.metric("Bookings today", "19", "+5 vs last Tuesday")

    st.divider()

    # quick price lookup
    st.markdown("### 🔍 Quick price lookup")
    st.caption("See what Parkzy would charge for a spot right now")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        zone = st.selectbox("Neighbourhood", list(LA_METER_RATES.keys()), index=4)
    with col_b:
        scenario = st.selectbox("Situation", [
            "Regular day, quiet",
            "Busy evening, no event",
            "Game day — 3 hrs out",
            "Concert — 1 hr out (sold out)",
        ])
    with col_c:
        st.markdown("<br>", unsafe_allow_html=True)
        run = st.button("Get price →", type="primary", use_container_width=True)

    scenario_params = {
        "Regular day, quiet":              dict(active_users=40,  listed_spots=30, hours_to_event=999, event_size=0.0, day_of_week=2, hour=14),
        "Busy evening, no event":          dict(active_users=120, listed_spots=20, hours_to_event=999, event_size=0.0, day_of_week=4, hour=19),
        "Game day — 3 hrs out":            dict(active_users=280, listed_spots=15, hours_to_event=3,   event_size=0.7, day_of_week=5, hour=17),
        "Concert — 1 hr out (sold out)":   dict(active_users=450, listed_spots=8,  hours_to_event=1,   event_size=1.0, day_of_week=6, hour=19),
    }

    if run:
        params = scenario_params[scenario]
        r = pricer.price(zone=zone, temperature=72, **params)
        meter = LA_METER_RATES.get(zone, LA_METER_RATES["default"])
        savings = meter - r["final_price"]

        rc1, rc2 = st.columns([1, 2])
        with rc1:
            st.markdown(f"<p class='price-label'>Parkzy recommended price</p><p class='big-price'>${r['final_price']:.2f}<span style='font-size:1.2rem;color:#888'>/hr</span></p>", unsafe_allow_html=True)
            if savings > 0:
                st.markdown(f"<span class='badge-green'>✓ ${savings:.2f}/hr cheaper than street meter</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"<span class='badge-orange'>⚡ Peak surge pricing active</span>", unsafe_allow_html=True)

        with rc2:
            m1, m2, m3 = st.columns(3)
            m1.metric("Base rate", f"${r['base']:.2f}", help="LA meter average for this zone × 0.85")
            m2.metric("Surge multiplier", f"{r['surge_mult']:.1f}×", help="How much the ML bumped the price based on demand")
            m3.metric("Street meter", f"${meter:.2f}", help="What you'd pay at a LADOT meter nearby")

            demand = r["active_users"] / max(r["listed_spots"], 1)
            level = "🔴 Very high" if demand > 10 else "🟠 High" if demand > 5 else "🟡 Medium" if demand > 2 else "🟢 Low"
            st.progress(min(demand / 15, 1.0), text=f"Demand pressure: {level}  ({demand:.1f}× more searchers than spots)")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: HOMEOWNER PORTAL
# ══════════════════════════════════════════════════════════════════════════════
with tab_homeowner:
    st.markdown("### Your parking spot, your rules")
    st.caption("Set a fixed rate, or let Parkzy's AI optimise pricing for you automatically")

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("#### 📍 Your spot details")
        owner_name  = st.text_input("Your name", value="Alex Johnson")
        spot_zone   = st.selectbox("Your neighbourhood", list(LA_METER_RATES.keys()), index=4)
        spot_desc   = st.text_input("Spot description", placeholder="e.g. Driveway, fits 1 car, covered")

        st.markdown("#### 💰 Pricing mode")

        pricing_mode = st.radio(
            "How do you want to price your spot?",
            ["🤖  Let Parkzy AI set the price", "✏️  I'll set my own fixed rate"],
            help="AI mode earns you more on event days. Fixed rate gives you full control.",
        )

        if pricing_mode == "✏️  I'll set my own fixed rate":
            fixed_rate = st.number_input(
                "Your fixed rate ($/hr)",
                min_value=1.0, max_value=50.0, value=5.0, step=0.50,
                help="This is what every driver will be charged, regardless of demand or events."
            )
            floor_override = None
            st.markdown(f"<span class='badge-blue'>Fixed at ${fixed_rate:.2f}/hr</span>", unsafe_allow_html=True)
        else:
            fixed_rate = None
            st.markdown("AI pricing is **on**. Your rate adjusts automatically based on demand and nearby events.")
            floor_override = st.slider(
                "Minimum price you'll accept ($/hr)",
                min_value=1.0, max_value=20.0, value=3.0, step=0.50,
                help="Parkzy will never price your spot below this, even when it's quiet."
            )

        st.markdown("#### 🕐 Availability")
        avail_days = st.multiselect(
            "Available days",
            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            default=["Fri", "Sat", "Sun"]
        )
        avail_hours = st.slider("Available hours", 0, 23, (14, 23), help="24h format")

        calculate = st.button("📊 See my earnings estimate", type="primary", use_container_width=True)

    with col_right:
        st.markdown("#### 📈 Your earnings preview")

        if calculate:
            scenarios = [
                ("Quiet weekday",        dict(active_users=40,  listed_spots=25, hours_to_event=999, event_size=0.0, day_of_week=2, hour=14)),
                ("Busy Friday evening",  dict(active_users=130, listed_spots=18, hours_to_event=999, event_size=0.0, day_of_week=4, hour=19)),
                ("Lakers game day",      dict(active_users=290, listed_spots=12, hours_to_event=3,   event_size=0.7, day_of_week=5, hour=17)),
                ("Taylor Swift concert", dict(active_users=480, listed_spots=7,  hours_to_event=1,   event_size=1.0, day_of_week=6, hour=19)),
            ]

            rows = []
            for label, params in scenarios:
                if fixed_rate is not None:
                    ai_r    = pricer.price(zone=spot_zone, temperature=72, **params)
                    your_rate = fixed_rate
                    ai_rate   = ai_r["final_price"]
                else:
                    ai_r    = pricer.price(zone=spot_zone, temperature=72, **params)
                    your_rate = max(ai_r["final_price"], floor_override or 1.5)
                    ai_rate   = your_rate

                rows.append({
                    "Scenario":       label,
                    "Your rate ($/hr)": f"${your_rate:.2f}",
                    "AI rate ($/hr)":  f"${ai_rate:.2f}",
                    "Est. 3hr session": f"${your_rate * 3:.2f}",
                })

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # monthly estimate
            sessions_per_month = len(avail_days) * 4 * 1.5  # rough avg
            avg_rate = fixed_rate if fixed_rate else (floor_override or 3.0) * 1.4
            monthly = sessions_per_month * avg_rate * 2.5

            st.markdown("---")
            st.markdown(f"<p class='price-label'>Estimated monthly earnings</p><p class='big-price'>${monthly:.0f}</p>", unsafe_allow_html=True)
            st.caption(f"Based on ~{sessions_per_month:.0f} sessions/month across {len(avail_days)} days · avg {avail_hours[1]-avail_hours[0]} hr window")

            if fixed_rate is not None:
                ai_avg = np.mean([
                    pricer.price(zone=spot_zone, temperature=72, **p)["final_price"]
                    for _, p in scenarios
                ])
                if ai_avg > fixed_rate:
                    uplift = (ai_avg - fixed_rate) * sessions_per_month * 2.5
                    st.info(f"💡 Switching to AI pricing could earn you an extra **${uplift:.0f}/month** on average — especially on event days.")
        else:
            st.markdown("""
            <div style='background:#f8f9fb; border-radius:12px; padding:2rem; text-align:center; color:#888; margin-top:2rem;'>
                <p style='font-size:2rem'>💸</p>
                <p>Fill in your details and hit <strong>See my earnings estimate</strong></p>
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: EVENTS & ALERTS
# ══════════════════════════════════════════════════════════════════════════════
with tab_events:
    st.markdown("### 🎤 Upcoming events near your spot")
    st.caption("Parkzy monitors events at nearby venues and alerts homeowners before demand spikes")

    if st.button("🔄  Refresh events", use_container_width=False):
        with st.spinner("Checking nearby venues…"):
            events = fetch_upcoming_events(api_key=None)
            st.session_state["events"] = events
            st.session_state["alerts"] = homeowner_alerts(events)

    if "events" not in st.session_state:
        with st.spinner("Loading events…"):
            st.session_state["events"] = fetch_upcoming_events(api_key=None)
            st.session_state["alerts"] = homeowner_alerts(st.session_state["events"])

    events = st.session_state["events"]
    alerts = st.session_state["alerts"]

    # event cards
    cols = st.columns(len(events))
    for i, ev in enumerate(events):
        with cols[i]:
            ds = ev["demand_score"]
            color = "#fff1f0" if ds > 0.6 else "#fffbeb" if ds > 0.3 else "#f0fdf4"
            border = "#ef4444" if ds > 0.6 else "#f59e0b" if ds > 0.3 else "#22c55e"
            badge = "🔥 High demand" if ds > 0.6 else "📈 Medium" if ds > 0.3 else "😴 Low"
            st.markdown(f"""
            <div style='background:{color}; border:1px solid {border}; border-radius:12px; padding:1rem;'>
                <p style='font-weight:700; margin:0; font-size:0.95rem;'>{ev['name']}</p>
                <p style='color:#666; font-size:0.8rem; margin:0.2rem 0;'>📍 {ev['venue']}</p>
                <p style='color:#666; font-size:0.8rem; margin:0;'>⏱ In {ev['hours_until']:.0f} hrs · {ev['capacity']:,} cap.</p>
                <p style='margin-top:0.5rem; font-size:0.8rem;'>{badge}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("### 📱 Homeowner alerts")
    if alerts:
        for a in alerts:
            css_class = "notif-high" if a["alert_level"] == "high" else "notif-med"
            icon = "🔥" if a["alert_level"] == "high" else "📍"
            st.markdown(f"""
            <div class='{css_class}'>
                <strong>{icon} {a['name']}</strong><br>
                <span style='font-size:0.9rem'>{a['message']}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("✅ No high-demand events right now — prices are at base rate.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: HOW THE AI WORKS — non-technical explainer
# ══════════════════════════════════════════════════════════════════════════════
with tab_how:
    st.markdown("### 🧠 How Parkzy's pricing AI works")
    st.caption("A plain-English explanation of the three layers under the hood")

    st.markdown("""
    <div class='card'>
        <h4 style='margin-top:0'>Layer 1 — Base price anchor 🏷️</h4>
        <p>Every spot starts from the average LADOT street meter rate for its neighbourhood.
        We automatically price <strong>15% below that</strong> so Parkzy is always the better deal for drivers —
        no homeowner has to think about this, it's baked in.</p>
        <p style='color:#888; font-size:0.85rem'>Example: Inglewood meters average $2.50/hr → Parkzy base = $2.12/hr</p>
    </div>

    <div class='card'>
        <h4 style='margin-top:0'>Layer 2 — Surge model 📈</h4>
        <p>A machine learning model watches <strong>8 real-time signals</strong> and predicts how much demand
        justifies raising the price above base. It was trained on thousands of scenarios and learned
        patterns like "320 people searching, 12 spots available, Saturday night, 2 hours before a
        stadium event = 3× price".</p>
        <p>The signals it weighs, in order of importance:</p>
    </div>
    """, unsafe_allow_html=True)

    fi = pricer.surge_model.feature_importances()
    df_fi = pd.DataFrame({
        "Signal": [
            "Active users searching",
            "Hours until event",
            "Event size",
            "Hour of day",
            "Spots available",
            "Day of week",
            "Weekend",
            "Temperature",
        ],
        "Weight": list(fi.values()),
        "Plain English": [
            "More people searching = higher price",
            "Closer to event = bigger surge",
            "Bigger venue = bigger surge",
            "Evening rush hours cost more",
            "Fewer spots = higher price",
            "Weekends naturally busier",
            "Weekend bonus applied",
            "Hot days reduce walking = higher demand",
        ]
    }).sort_values("Weight", ascending=False)

    df_fi["Weight %"] = (df_fi["Weight"] * 100).round(1).astype(str) + "%"
    st.dataframe(df_fi[["Signal", "Weight %", "Plain English"]], use_container_width=True, hide_index=True)

    st.markdown("""
    <div class='card' style='margin-top:1rem'>
        <h4 style='margin-top:0'>Layer 3 — Self-learning loop 🤖</h4>
        <p>This is what makes Parkzy smarter over time. After every booking (or missed booking),
        the system gets a signal:</p>
        <ul>
            <li>✅ <strong>Spot booked</strong> → the price was right, remember this</li>
            <li>❌ <strong>Spot sat empty</strong> → too expensive, nudge it down next time</li>
            <li>⚡ <strong>Booked instantly</strong> → could have charged more, note that</li>
        </ul>
        <p>Over thousands of real bookings, the AI builds a map of exactly what to charge
        in every situation — without anyone programming those rules manually.</p>
        <p style='color:#888; font-size:0.85rem'>Technical name: Epsilon-greedy reinforcement learning with a Q-table.
        Exploration rate 15% — meaning 1 in 7 pricing decisions tries something new to keep learning.</p>
    </div>
    """, unsafe_allow_html=True)

    # live demo of the RL table
    st.markdown("#### Live learning table")
    st.caption("This is the AI's current best guess for price adjustments by situation — it updates every booking")

    df_q = pricer.rl.policy_summary()
    if not df_q.empty:
        df_q["Demand level"] = df_q["state"].apply(lambda s: ["Very low","Low","Medium","High","Very high"][min(int(s.split("_")[0]),4)])
        df_q["Event proximity"] = df_q["state"].apply(lambda s: {0:"No event nearby", 1:"Event in 3-12 hrs", 2:"Event in <3 hrs"}[int(s.split("_")[1])])
        df_q["Price adjustment"] = df_q["best_delta"].apply(lambda d: f"{'▲' if d>0 else '▼' if d<0 else '—'} {abs(d):.2f}×")
        st.dataframe(
            df_q[["Demand level","Event proximity","Price adjustment"]],
            use_container_width=True, hide_index=True
        )