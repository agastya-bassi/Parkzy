"""
Parkzy – Streamlit Demo  (dark AI startup edition)
Run: streamlit run app.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import pandas as pd
import numpy as np

from pricing_engine import (
    ParkSharePricer, fetch_upcoming_events,
    homeowner_alerts, LA_METER_RATES,
)

# ── page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Parkzy", page_icon="🅿️",
                   layout="wide", initial_sidebar_state="collapsed")

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

/* ── reset & base ── */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #0a0710 !important;
    color: #ede9fe !important;
}
.block-container {
    padding-top: 1.8rem !important;
    padding-bottom: 2rem !important;
    max-width: 1120px !important;
    background: transparent !important;
}
section[data-testid="stSidebar"] { background: #0d0a17 !important; }

/* ── scrollbar ── */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: #0d0a17; }
::-webkit-scrollbar-thumb { background: #3b1f6a; border-radius: 4px; }

/* ── logo / header ── */
.park-logo {
    font-family: 'Syne', sans-serif;
    font-size: 2rem; font-weight: 800;
    background: linear-gradient(135deg, #c084fc 0%, #a855f7 50%, #e879f9 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    letter-spacing: -0.03em; line-height: 1;
}
.park-tagline {
    font-size: 0.82rem; color: #6b21a8; letter-spacing: 0.06em;
    text-transform: uppercase; margin-top: 2px;
}

/* ── tabs ── */
[data-baseweb="tab-list"] {
    background: #12082a !important;
    border-radius: 12px !important;
    padding: 4px !important;
    border: 1px solid #2d1a5e !important;
    gap: 2px !important;
}
button[data-baseweb="tab"] {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.85rem !important; font-weight: 500 !important;
    color: #6b21a8 !important;
    border-radius: 8px !important;
    padding: 0.45rem 1.1rem !important;
    transition: all 0.2s !important;
}
button[data-baseweb="tab"]:hover { color: #c084fc !important; background: #1a0a35 !important; }
button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #2d1a5e, #3b1070) !important;
    color: #e879f9 !important;
    border: 1px solid #a855f744 !important;
}

/* ── glass card ── */
.gcard {
    background: linear-gradient(135deg, #12082a 0%, #0e0520 100%);
    border: 1px solid #2d1a5e;
    border-radius: 16px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1rem;
    position: relative;
    overflow: hidden;
}
.gcard::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, #a855f733, #e879f922, transparent);
}
.gcard h4 {
    font-family: 'Syne', sans-serif;
    color: #ede9fe; font-size: 1rem; font-weight: 700;
    margin: 0 0 0.6rem 0; letter-spacing: -0.01em;
}
.gcard p, .gcard li { color: #a78bfa; font-size: 0.9rem; line-height: 1.65; margin: 0 0 0.5rem 0; }
.gcard strong { color: #ddd6fe; }
.gcard ul { padding-left: 1.2rem; }
.gcard .sub { color: #4c1d95; font-size: 0.8rem; margin-top: 0.4rem; }

/* ── kpi card ── */
.kpi {
    background: linear-gradient(135deg, #12082a, #0e0520);
    border: 1px solid #2d1a5e;
    border-radius: 14px; padding: 1.1rem 1.3rem;
    position: relative; overflow: hidden;
}
.kpi::after {
    content: ''; position: absolute;
    bottom: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #a855f7, #e879f9);
    opacity: 0.6;
}
.kpi-val {
    font-family: 'Syne', sans-serif;
    font-size: 1.9rem; font-weight: 800; color: #ede9fe;
    line-height: 1.1; letter-spacing: -0.03em;
}
.kpi-label { font-size: 0.75rem; color: #6b21a8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
.kpi-delta { font-size: 0.78rem; color: #c084fc; margin-top: 3px; }

/* ── big price ── */
.big-price {
    font-family: 'Syne', sans-serif;
    font-size: 4rem; font-weight: 800; letter-spacing: -0.04em;
    background: linear-gradient(135deg, #c084fc, #e879f9);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    line-height: 1;
}
.price-unit { font-size: 1.1rem; color: #6b21a8; font-weight: 400; }
.price-label { font-size: 0.75rem; color: #6b21a8; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px; }

/* ── badges ── */
.badge {
    display: inline-block; padding: 3px 11px;
    border-radius: 20px; font-size: 0.75rem; font-weight: 600;
    letter-spacing: 0.02em;
}
.badge-cyan   { background: #1a0a35; color: #c084fc; border: 1px solid #a855f733; }
.badge-green  { background: #0f1a0a; color: #86efac; border: 1px solid #86efac22; }
.badge-orange { background: #2d1a05; color: #fb923c; border: 1px solid #fb923c22; }
.badge-red    { background: #2d0505; color: #f87171; border: 1px solid #f8717122; }
.badge-purple { background: #2d1a5e; color: #e879f9; border: 1px solid #e879f933; }

/* ── section title ── */
.sec-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.35rem; font-weight: 700; color: #ede9fe;
    letter-spacing: -0.02em; margin-bottom: 2px;
}
.sec-sub { font-size: 0.82rem; color: #6b21a8; margin-bottom: 1.2rem; }

/* ── divider ── */
.glowdiv {
    height: 1px; margin: 1.2rem 0;
    background: linear-gradient(90deg, transparent, #4c1d95, transparent);
}

/* ── event card ── */
.evcard {
    background: #12082a; border: 1px solid #2d1a5e;
    border-radius: 14px; padding: 1rem 1.1rem;
    transition: border-color 0.2s;
}
.evcard-hot  { border-color: #ef444433 !important; background: #1a0a15 !important; }
.evcard-warm { border-color: #f59e0b33 !important; background: #1a1005 !important; }
.evcard-cool { border-color: #a855f733 !important; }
.evcard-name { font-family: 'Syne', sans-serif; font-weight: 700; font-size: 0.92rem; color: #ede9fe; margin: 0 0 4px 0; }
.evcard-meta { font-size: 0.78rem; color: #6b21a8; margin: 1px 0; }

/* ── notif ── */
.notif {
    border-radius: 12px; padding: 1rem 1.2rem; margin: 0.5rem 0;
    border-left: 3px solid;
}
.notif-high { background: #1a0a15; border-color: #ef4444; }
.notif-med  { background: #1a1005; border-color: #f59e0b; }
.notif strong { color: #ede9fe; font-family: 'Syne', sans-serif; }
.notif span   { color: #a78bfa; font-size: 0.88rem; }

/* ── streamlit overrides ── */
[data-testid="metric-container"] {
    background: #12082a !important;
    border: 1px solid #2d1a5e !important;
    border-radius: 12px !important; padding: 1rem 1.2rem !important;
}
[data-testid="metric-container"] label { color: #6b21a8 !important; font-size: 0.75rem !important; }
[data-testid="stMetricValue"]          { color: #ede9fe !important; font-family: 'Syne', sans-serif !important; font-size: 1.5rem !important; }
[data-testid="stMetricDelta"]          { color: #c084fc !important; }
[data-testid="stDataFrame"]            { background: #12082a !important; border-radius: 12px !important; }
div[data-testid="stDataFrameResizable"] > div { background: #12082a !important; }
.stDataFrame th { background: #1a0a35 !important; color: #7c3aed !important; font-size: 0.78rem !important; }
.stDataFrame td { color: #a78bfa !important; font-size: 0.85rem !important; }

/* inputs */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div { background: #12082a !important; border-color: #2d1a5e !important; color: #ede9fe !important; border-radius: 10px !important; }
label[data-testid="stWidgetLabel"] p { color: #7c3aed !important; font-size: 0.8rem !important; }
.stSlider [data-testid="stTickBarMin"], .stSlider [data-testid="stTickBarMax"] { color: #6b21a8 !important; }
.stSlider div[role="slider"] { background: #a855f7 !important; }
div[data-baseweb="radio"] label p { color: #a78bfa !important; }

/* buttons */
.stButton > button {
    background: linear-gradient(135deg, #2d1a5e, #3b1070) !important;
    color: #c084fc !important; border: 1px solid #a855f744 !important;
    border-radius: 10px !important; font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important; transition: all 0.2s !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #7c3aed, #9333ea) !important;
    color: white !important; border-color: transparent !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #7c3aed, #9333ea) !important;
    color: white !important; border: none !important;
}
.stButton > button[kind="primary"]:hover { opacity: 0.9 !important; }

/* progress bar */
.stProgress > div > div { background: linear-gradient(90deg, #a855f7, #e879f9) !important; }

/* info / success */
.stAlert { background: #12082a !important; border-radius: 12px !important; border-color: #2d1a5e !important; color: #a78bfa !important; }

/* hide branding */
#MainMenu, footer, header { visibility: hidden !important; }
</style>
""", unsafe_allow_html=True)

# ── init ──────────────────────────────────────────────────────────────────────
@st.cache_resource
def get_pricer():
    p = ParkSharePricer(model_dir="/tmp/parkzy_v2")
    p.simulate_rl_training(n=300)
    return p

pricer = get_pricer()

# ── header ────────────────────────────────────────────────────────────────────
c1, c2 = st.columns([1, 4])
with c1:
    st.markdown("<div class='park-logo'>🅿 Parkzy</div><div class='park-tagline'>Inglewood · USC · AI-powered parking</div>", unsafe_allow_html=True)
with c2:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    b1, b2, b3, b4 = st.columns(4)
    b1.markdown("<div class='kpi'><div class='kpi-label'>Drivers searching</div><div class='kpi-val'>247</div><div class='kpi-delta'>↑ 18 this hour</div></div>", unsafe_allow_html=True)
    b2.markdown("<div class='kpi'><div class='kpi-label'>Spots listed</div><div class='kpi-val'>34</div><div class='kpi-delta'>↑ 6 today</div></div>", unsafe_allow_html=True)
    b3.markdown("<div class='kpi'><div class='kpi-label'>Avg price / hr</div><div class='kpi-val'>$4.20</div><div class='kpi-delta'>↑ $0.80 vs yesterday</div></div>", unsafe_allow_html=True)
    b4.markdown("<div class='kpi'><div class='kpi-label'>Bookings today</div><div class='kpi-val'>19</div><div class='kpi-delta'>↑ 5 vs last Tue</div></div>", unsafe_allow_html=True)

st.markdown("<div class='glowdiv' style='margin:1.4rem 0'></div>", unsafe_allow_html=True)

# ── tabs ──────────────────────────────────────────────────────────────────────
tab_home, tab_homeowner, tab_events, tab_how = st.tabs([
    "⚡  Live Pricing",
    "🏠  Homeowner Portal",
    "🎤  Events & Alerts",
    "🧠  How the AI Works",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — LIVE PRICING
# ══════════════════════════════════════════════════════════════════════════════
with tab_home:
    st.markdown("<div class='sec-title'>Live price calculator</div><div class='sec-sub'>Pick a scenario and see the AI price in real time</div>", unsafe_allow_html=True)

    col_in, col_out = st.columns([1, 1], gap="large")

    with col_in:
        st.markdown("<div class='gcard'><h4>📍 Scenario inputs</h4>", unsafe_allow_html=True)
        zone     = st.selectbox("Neighbourhood", list(LA_METER_RATES.keys()), index=4)
        scenario = st.selectbox("Quick scenario", [
            "Regular day, quiet",
            "Busy evening, no event",
            "Game day — 3 hrs out",
            "Concert — 1 hr out (sold out)",
            "Custom →",
        ])
        st.markdown("</div>", unsafe_allow_html=True)

        scenario_params = {
            "Regular day, quiet":            dict(active_users=40,  listed_spots=30, hours_to_event=999, event_size=0.0, day_of_week=2, hour=14),
            "Busy evening, no event":        dict(active_users=120, listed_spots=20, hours_to_event=999, event_size=0.0, day_of_week=4, hour=19),
            "Game day — 3 hrs out":          dict(active_users=280, listed_spots=15, hours_to_event=3,   event_size=0.7, day_of_week=5, hour=17),
            "Concert — 1 hr out (sold out)": dict(active_users=450, listed_spots=8,  hours_to_event=1,   event_size=1.0, day_of_week=6, hour=19),
        }

        if scenario == "Custom →":
            st.markdown("<div class='gcard'><h4>🎛 Custom inputs</h4>", unsafe_allow_html=True)
            active_users   = st.slider("Active users searching", 5, 600, 80)
            listed_spots   = st.slider("Spots available", 1, 100, 20)
            hours_to_event = st.slider("Hours to nearest event", 0.0, 48.0, 4.0, step=0.5)
            event_size     = st.slider("Event size (0 = small, 1 = sold-out)", 0.0, 1.0, 0.6)
            hour           = st.slider("Hour of day", 0, 23, 18)
            dow            = st.selectbox("Day", ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"], index=5)
            params = dict(active_users=active_users, listed_spots=listed_spots,
                          hours_to_event=hours_to_event if hours_to_event < 48 else 999,
                          event_size=event_size, day_of_week=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].index(dow), hour=hour)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            params = scenario_params[scenario]

        run = st.button("⚡  Calculate price", type="primary", use_container_width=True)

    with col_out:
        if run or "last_r" in st.session_state:
            if run:
                r = pricer.price(zone=zone, temperature=72, **params)
                st.session_state["last_r"] = r
                st.session_state["last_zone"] = zone
            r    = st.session_state["last_r"]
            zone = st.session_state.get("last_zone", zone)
            meter = LA_METER_RATES.get(zone, LA_METER_RATES["default"])
            savings = meter - r["final_price"]
            demand  = r["active_users"] / max(r["listed_spots"], 1)

            st.markdown(f"""
            <div class='gcard' style='text-align:center; padding: 2rem 1.5rem;'>
                <div class='price-label'>AI recommended price</div>
                <div class='big-price'>${r['final_price']:.2f}</div>
                <div style='color:#475569; font-size:0.9rem; margin-top:4px'>per hour</div>
                <div style='margin-top:1rem'>
                    {'<span class="badge badge-green">✓ ${:.2f}/hr below street meter</span>'.format(savings) if savings > 0 else '<span class="badge badge-orange">⚡ Peak surge active</span>'}
                </div>
            </div>
            """, unsafe_allow_html=True)

            m1, m2, m3 = st.columns(3)
            m1.metric("Base rate",        f"${r['base']:.2f}",        help="Meter avg × 0.85")
            m2.metric("Surge multiplier", f"{r['surge_mult']:.1f}×",  help="ML demand boost")
            m3.metric("Street meter",     f"${meter:.2f}",             help="LADOT rate nearby")

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            d_pct = min(demand / 15, 1.0)
            level = "🔴 Very high" if demand > 10 else "🟠 High" if demand > 5 else "🟡 Medium" if demand > 2 else "🟢 Low"
            st.progress(d_pct, text=f"Demand pressure: {level}  ·  {demand:.1f}× more searchers than spots")

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            cb1, cb2 = st.columns(2)
            with cb1:
                if st.button("✅ Spot was booked", use_container_width=True):
                    pricer.record_outcome(True, r["final_price"] * 2)
                    st.success("RL updated — reward logged!")
            with cb2:
                if st.button("❌ No booking", use_container_width=True):
                    pricer.record_outcome(False, 0)
                    st.info("RL updated — penalty logged.")
        else:
            st.markdown("""
            <div class='gcard' style='text-align:center; padding:3rem 1.5rem;'>
                <div style='font-size:3rem; margin-bottom:1rem'>⚡</div>
                <div style='font-family:Syne,sans-serif; font-size:1.1rem; color:#334155; font-weight:600'>
                    Set a scenario and hit Calculate
                </div>
                <div style='color:#1e2d45; font-size:0.85rem; margin-top:0.5rem'>
                    AI price appears here instantly
                </div>
            </div>
            """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — HOMEOWNER PORTAL
# ══════════════════════════════════════════════════════════════════════════════
with tab_homeowner:
    st.markdown("<div class='sec-title'>Homeowner portal</div><div class='sec-sub'>Your spot, your rules — AI-optimised or fixed rate</div>", unsafe_allow_html=True)

    col_l, col_r = st.columns([1, 1], gap="large")

    with col_l:
        st.markdown("<div class='gcard'><h4>📍 Spot details</h4>", unsafe_allow_html=True)
        owner_name = st.text_input("Your name", value="Alex Johnson")
        spot_zone  = st.selectbox("Neighbourhood", list(LA_METER_RATES.keys()), index=4)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='gcard'><h4>💰 Pricing mode</h4>", unsafe_allow_html=True)
        pricing_mode = st.radio("", [
            "🤖  AI sets the price automatically",
            "✏️  I'll set my own fixed rate",
        ], label_visibility="collapsed")

        if "fixed" in pricing_mode:
            fixed_rate = st.number_input("Your fixed rate ($/hr)", 1.0, 50.0, 5.0, step=0.5)
            floor_override = None
            st.markdown(f"<span class='badge badge-cyan'>Locked at ${fixed_rate:.2f}/hr</span>", unsafe_allow_html=True)
        else:
            fixed_rate = None
            floor_override = st.slider("Minimum you'll accept ($/hr)", 1.0, 20.0, 3.0, step=0.5)
            st.markdown(f"<span class='badge badge-purple'>AI pricing · floor ${floor_override:.2f}/hr</span>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='gcard'><h4>🕐 Availability</h4>", unsafe_allow_html=True)
        avail_days  = st.multiselect("Available days", ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"], default=["Fri","Sat","Sun"])
        avail_hours = st.slider("Hours available", 0, 23, (14, 23))
        st.markdown("</div>", unsafe_allow_html=True)

        go = st.button("📊  See earnings estimate", type="primary", use_container_width=True)

    with col_r:
        if go:
            scenarios = [
                ("Quiet weekday",        dict(active_users=40,  listed_spots=25, hours_to_event=999, event_size=0.0, day_of_week=2, hour=14)),
                ("Busy Friday evening",  dict(active_users=130, listed_spots=18, hours_to_event=999, event_size=0.0, day_of_week=4, hour=19)),
                ("Lakers game day",      dict(active_users=290, listed_spots=12, hours_to_event=3,   event_size=0.7, day_of_week=5, hour=17)),
                ("Taylor Swift concert", dict(active_users=480, listed_spots=7,  hours_to_event=1,   event_size=1.0, day_of_week=6, hour=19)),
            ]
            rows = []
            for label, p in scenarios:
                ai_r = pricer.price(zone=spot_zone, temperature=72, **p)
                your = fixed_rate if fixed_rate else max(ai_r["final_price"], floor_override or 1.5)
                rows.append({"Scenario": label, "Your rate": f"${your:.2f}/hr", "AI rate": f"${ai_r['final_price']:.2f}/hr", "3hr session": f"${your*3:.2f}"})

            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            sessions = len(avail_days) * 4 * 1.5
            avg_r    = fixed_rate if fixed_rate else (floor_override or 3.0) * 1.4
            monthly  = sessions * avg_r * 2.5

            st.markdown(f"""
            <div class='gcard' style='text-align:center; margin-top:1rem'>
                <div class='price-label'>Estimated monthly earnings</div>
                <div class='big-price'>${monthly:.0f}</div>
                <div style='color:#475569; font-size:0.82rem; margin-top:6px'>
                    ~{sessions:.0f} sessions · {len(avail_days)} days/wk · {avail_hours[1]-avail_hours[0]}hr window
                </div>
            </div>
            """, unsafe_allow_html=True)

            if fixed_rate:
                ai_avg = np.mean([pricer.price(zone=spot_zone, temperature=72, **p)["final_price"] for _, p in scenarios])
                if ai_avg > fixed_rate:
                    uplift = (ai_avg - fixed_rate) * sessions * 2.5
                    st.markdown(f"<div class='gcard'><span class='badge badge-green'>💡 Tip</span><p style='margin-top:0.5rem'>Switching to AI pricing could earn you an extra <strong style='color:#34d399'>${uplift:.0f}/month</strong> — especially on event days.</p></div>", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class='gcard' style='text-align:center; padding:3rem 1.5rem; margin-top:2rem'>
                <div style='font-size:3rem; margin-bottom:1rem'>💸</div>
                <div style='font-family:Syne,sans-serif; color:#334155; font-weight:600'>
                    Fill in your details and hit<br>See earnings estimate
                </div>
            </div>
            """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — EVENTS & ALERTS
# ══════════════════════════════════════════════════════════════════════════════
with tab_events:
    st.markdown("<div class='sec-title'>Events & homeowner alerts</div><div class='sec-sub'>Parkzy watches nearby venues and tells homeowners when to list</div>", unsafe_allow_html=True)

    if st.button("🔄  Refresh", use_container_width=False):
        with st.spinner("Scanning venues…"):
            st.session_state["events"] = fetch_upcoming_events()
            st.session_state["alerts"] = homeowner_alerts(st.session_state["events"])

    if "events" not in st.session_state:
        st.session_state["events"] = fetch_upcoming_events()
        st.session_state["alerts"] = homeowner_alerts(st.session_state["events"])

    events = st.session_state["events"]
    alerts = st.session_state["alerts"]

    cols = st.columns(len(events))
    for i, ev in enumerate(events):
        ds = ev["demand_score"]
        cls = "evcard-hot" if ds > 0.6 else "evcard-warm" if ds > 0.3 else "evcard-cool"
        badge = f"<span class='badge badge-red'>🔥 High demand</span>" if ds > 0.6 \
           else f"<span class='badge badge-orange'>📈 Medium</span>" if ds > 0.3 \
           else f"<span class='badge badge-cyan'>😴 Low</span>"
        with cols[i]:
            st.markdown(f"""
            <div class='evcard {cls}'>
                <p class='evcard-name'>{ev['name']}</p>
                <p class='evcard-meta'>📍 {ev['venue']}</p>
                <p class='evcard-meta'>⏱ In {ev['hours_until']:.0f} hrs</p>
                <p class='evcard-meta'>👥 {ev['capacity']:,} capacity</p>
                <div style='margin-top:0.6rem'>{badge}</div>
                <div style='margin-top:0.4rem; font-size:0.72rem; color:#334155'>
                    Demand score: {ds:.2f} / 1.00
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div class='glowdiv'></div>", unsafe_allow_html=True)
    st.markdown("<div class='sec-title' style='font-size:1.1rem'>📱 Homeowner notification queue</div>", unsafe_allow_html=True)

    if alerts:
        for a in alerts:
            cls  = "notif-high" if a["alert_level"] == "high" else "notif-med"
            icon = "🔥" if a["alert_level"] == "high" else "📍"
            st.markdown(f"""
            <div class='notif {cls}'>
                <strong>{icon} {a['name']}</strong><br>
                <span>{a['message']}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("<div class='gcard'><p>✅ No high-demand events right now — prices are at base rate.</p></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — HOW THE AI WORKS
# ══════════════════════════════════════════════════════════════════════════════
with tab_how:
    st.markdown("<div class='sec-title'>How the AI works</div><div class='sec-sub'>Three layers that price every spot automatically</div>", unsafe_allow_html=True)

    st.markdown("""
    <div class='gcard'>
        <h4>Layer 1 — Base price anchor 🏷️</h4>
        <p>Every spot starts from the average LADOT street meter rate for its zone.
        We automatically price <strong>15% below that</strong> — so Parkzy is always the cheaper option,
        baked into the math, no homeowner has to think about it.</p>
        <p class='sub'>Inglewood meters avg $2.50/hr → Parkzy base = $2.12/hr</p>
    </div>
    <div class='gcard'>
        <h4>Layer 2 — Surge model 📈</h4>
        <p>A gradient boosted ML model trained on thousands of scenarios predicts a surge multiplier
        based on 8 live signals. Pattern example: <strong>320 searchers, 12 spots, Saturday night,
        2 hrs before a stadium event = 3.2× price.</strong></p>
        <p>Signals it weighs, in order of importance:</p>
    </div>
    """, unsafe_allow_html=True)

    fi = pricer.surge_model.feature_importances()
    df_fi = pd.DataFrame({
        "Signal": ["Active users searching","Hours until event","Event size","Hour of day","Spots available","Day of week","Weekend","Temperature"],
        "Weight": list(fi.values()),
        "What it means": ["More demand = higher price","Closer to event = bigger surge","Bigger venue = bigger surge","Evening rush hours cost more","Fewer spots = higher price","Weekends naturally busier","Weekend bonus applied","Hot days reduce walking"],
    }).sort_values("Weight", ascending=False)
    df_fi["Weight %"] = (df_fi["Weight"]*100).round(1).astype(str) + "%"
    st.dataframe(df_fi[["Signal","Weight %","What it means"]], use_container_width=True, hide_index=True)

    st.markdown("""
    <div class='gcard' style='margin-top:1rem'>
        <h4>Layer 3 — Self-learning RL loop 🤖</h4>
        <p>After every session the system gets a reward or penalty signal and nudges its pricing strategy:</p>
        <ul>
            <li>✅ <strong>Spot booked</strong> → price was right, remember this</li>
            <li>❌ <strong>Spot sat empty</strong> → too expensive, nudge down next time</li>
            <li>⚡ <strong>Booked instantly</strong> → could have charged more</li>
        </ul>
        <p>Over thousands of real bookings the AI builds a map of what to charge in every situation — no manual rules needed.</p>
        <p class='sub'>Epsilon-greedy Q-table · ε=0.15 · α=0.10 · γ=0.90</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    st.markdown("<div class='sec-title' style='font-size:1rem; margin-bottom:4px'>Live learning table</div>", unsafe_allow_html=True)
    st.markdown("<div class='sec-sub'>Best price adjustment per situation — updates every booking</div>", unsafe_allow_html=True)

    df_q = pricer.rl.policy_summary()
    if not df_q.empty:
        df_q["Demand level"]    = df_q["state"].apply(lambda s: ["Very low","Low","Medium","High","Very high"][min(int(s.split("_")[0]),4)])
        df_q["Event proximity"] = df_q["state"].apply(lambda s: {0:"No event",1:"Event 3–12 hrs",2:"Event <3 hrs"}[int(s.split("_")[1])])
        df_q["Adjustment"]      = df_q["best_delta"].apply(lambda d: f"{'▲' if d>0 else '▼' if d<0 else '—'} {abs(d):.2f}×")
        st.dataframe(df_q[["Demand level","Event proximity","Adjustment"]], use_container_width=True, hide_index=True)