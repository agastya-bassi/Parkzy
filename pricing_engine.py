"""
ParkShare ML Pricing Engine
───────────────────────────
Base + Surge pricing with a self-improving RL reward loop.

Architecture
  1. BaseModel      – anchored to LA meter averages, undercuts by ~15 %
  2. SurgeModel     – gradient boosted regressor; features: active users,
                      hours to event, event_size, day_of_week, hour, weather
  3. RLFeedbackLoop – lightweight Q-table / epsilon-greedy bandit that
                      adjusts surge multiplier weights based on booking outcomes
  4. EventWatcher   – polls Ticketmaster / SeatGeek APIs, scores demand,
                      triggers homeowner notifications
"""

import json, os, pickle, random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

# ─────────────────────────────────────────────────
# 1. BASE PRICE MODEL
# ─────────────────────────────────────────────────

# LA metered parking averages by zone ($/hr) – sourced from LADOT open data
LA_METER_RATES = {
    "downtown":      4.00,
    "hollywood":     3.50,
    "inglewood":     2.50,
    "USC":           3.00,
    "culver_city":   2.00,
    "el_segundo":    1.75,
    "default":       2.75,
}

COMPETITOR_DISCOUNT = 0.85   # 15 % cheaper than street meters
FLOOR_PRICE         = 1.50   # never go below $1.50/hr
CEILING_PRICE       = 25.00  # hard cap; prevents gouging complaints

def base_price(zone: str = "inglewood") -> float:
    """Return the anchor base rate for a given zone."""
    meter = LA_METER_RATES.get(zone, LA_METER_RATES["default"])
    return round(meter * COMPETITOR_DISCOUNT, 2)


# ─────────────────────────────────────────────────
# 2. SURGE MODEL  (gradient boosted regressor)
# ─────────────────────────────────────────────────

SURGE_FEATURES = [
    "active_users",      # real-time users on app searching for a spot
    "listed_spots",      # supply side
    "hours_to_event",    # 0 = during event, 999 = no event
    "event_size",        # 0–1 scaled (stadium=1, club=0.2)
    "day_of_week",       # 0=Mon … 6=Sun
    "hour",              # 0–23
    "is_weekend",        # bool
    "temperature",       # F; people walk less in heat/rain
]


def _synthetic_training_data(n: int = 2000) -> pd.DataFrame:
    """
    Generate plausible synthetic rows.
    In production, replace with real booking history.
    """
    rng = np.random.default_rng(42)
    rows = []
    for _ in range(n):
        active_users   = int(rng.integers(5, 500))
        listed_spots   = int(rng.integers(1, 80))
        hours_to_event = float(rng.choice([999] * 6 + list(rng.uniform(0, 12, 4))))
        event_size     = 0.0 if hours_to_event == 999 else float(rng.uniform(0.1, 1.0))
        dow            = int(rng.integers(0, 7))
        hour           = int(rng.integers(6, 23))
        is_weekend     = int(dow >= 5)
        temp           = float(rng.uniform(55, 95))

        # Ground-truth multiplier: hand-crafted for synthetic data
        demand_ratio = active_users / max(listed_spots, 1)
        event_boost  = max(0, (1 - hours_to_event / 12)) * event_size * 2.5 if hours_to_event < 12 else 0
        weekend_bump = 0.15 * is_weekend
        peak_bump    = 0.20 if 17 <= hour <= 20 else 0
        multiplier   = 1.0 + 0.4 * np.log1p(demand_ratio) + event_boost + weekend_bump + peak_bump
        multiplier   = float(np.clip(multiplier + rng.normal(0, 0.05), 1.0, 3.5))

        rows.append({
            "active_users":    active_users,
            "listed_spots":    listed_spots,
            "hours_to_event":  hours_to_event,
            "event_size":      event_size,
            "day_of_week":     dow,
            "hour":            hour,
            "is_weekend":      is_weekend,
            "temperature":     temp,
            "surge_multiplier": multiplier,
        })
    return pd.DataFrame(rows)


class SurgeModel:
    """
    Gradient boosted regressor that predicts a surge multiplier.
    Persists itself to disk so it can be retrained incrementally.
    """

    def __init__(self, model_path: str = "surge_model.pkl"):
        self.model_path = Path(model_path)
        self.model   : GradientBoostingRegressor | None = None
        self.scaler  : StandardScaler | None = None
        self._load_or_train()

    # ── training ──────────────────────────────────

    def _load_or_train(self):
        if self.model_path.exists():
            with open(self.model_path, "rb") as f:
                payload = pickle.load(f)
            self.model  = payload["model"]
            self.scaler = payload["scaler"]
            print(f"[SurgeModel] Loaded from {self.model_path}")
        else:
            print("[SurgeModel] No checkpoint found — training on synthetic data …")
            df = _synthetic_training_data(2000)
            self._fit(df)

    def _fit(self, df: pd.DataFrame):
        X = df[SURGE_FEATURES].values
        y = df["surge_multiplier"].values
        self.scaler = StandardScaler().fit(X)
        Xs = self.scaler.transform(X)
        self.model = GradientBoostingRegressor(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            subsample=0.8, random_state=42
        )
        self.model.fit(Xs, y)
        self._save()

    def _save(self):
        with open(self.model_path, "wb") as f:
            pickle.dump({"model": self.model, "scaler": self.scaler}, f)
        print(f"[SurgeModel] Saved to {self.model_path}")

    def retrain(self, new_rows: pd.DataFrame):
        """Append new labelled rows and retrain. Called by RL loop."""
        existing = _synthetic_training_data(500)   # keep some base diversity
        combined = pd.concat([existing, new_rows], ignore_index=True)
        self._fit(combined)

    # ── inference ─────────────────────────────────

    def predict(self, features: dict) -> float:
        row = np.array([[features.get(f, 0) for f in SURGE_FEATURES]])
        Xs  = self.scaler.transform(row)
        mult = float(self.model.predict(Xs)[0])
        return round(np.clip(mult, 1.0, 3.5), 3)

    def feature_importances(self) -> dict:
        return dict(zip(SURGE_FEATURES, self.model.feature_importances_))


# ─────────────────────────────────────────────────
# 3. RL SELF-LEARNING FEEDBACK LOOP
# ─────────────────────────────────────────────────

class RLFeedbackLoop:
    """
    Lightweight epsilon-greedy bandit over a discrete set of
    surge-multiplier adjustment deltas.

    State  : (demand_bucket, event_bucket)   (coarse discretisation)
    Actions: adjust the raw model multiplier by one of DELTAS
    Reward : booking_completed * revenue_earned - vacancy_penalty

    Q-table is persisted to a JSON file for continuity across restarts.
    """

    DELTAS  = [-0.3, -0.15, 0.0, +0.15, +0.30]   # action space
    EPSILON = 0.15     # exploration rate
    ALPHA   = 0.10     # learning rate
    GAMMA   = 0.90     # discount factor

    def __init__(self, qtable_path: str = "qtable.json"):
        self.qtable_path = Path(qtable_path)
        self.q: dict = {}
        self._load()

    # ── persistence ───────────────────────────────

    def _load(self):
        if self.qtable_path.exists():
            with open(self.qtable_path) as f:
                self.q = json.load(f)

    def _save(self):
        with open(self.qtable_path, "w") as f:
            json.dump(self.q, f)

    # ── state discretisation ──────────────────────

    @staticmethod
    def _state(demand_ratio: float, hours_to_event: float) -> str:
        d = min(int(demand_ratio / 2), 4)           # 0-4 bucket
        e = 0 if hours_to_event > 12 else (1 if hours_to_event > 3 else 2)
        return f"{d}_{e}"

    def _q_row(self, state: str) -> list:
        if state not in self.q:
            self.q[state] = [0.0] * len(self.DELTAS)
        return self.q[state]

    # ── action selection ──────────────────────────

    def choose_delta(self, demand_ratio: float, hours_to_event: float) -> float:
        state = self._state(demand_ratio, hours_to_event)
        if random.random() < self.EPSILON:
            return random.choice(self.DELTAS)          # explore
        row = self._q_row(state)
        return self.DELTAS[int(np.argmax(row))]        # exploit

    # ── learning step ─────────────────────────────

    def update(
        self,
        demand_ratio: float,
        hours_to_event: float,
        delta_used: float,
        booking_completed: bool,
        revenue: float,
        vacancy_penalty: float = 0.50,
    ):
        """Call this after each booking window closes."""
        state  = self._state(demand_ratio, hours_to_event)
        action = self.DELTAS.index(delta_used)
        reward = (revenue if booking_completed else -vacancy_penalty)

        row       = self._q_row(state)
        old_q     = row[action]
        row[action] = old_q + self.ALPHA * (reward + self.GAMMA * max(row) - old_q)
        self.q[state] = row
        self._save()

    def policy_summary(self) -> pd.DataFrame:
        """Return best action per state for inspection."""
        rows = []
        for state, q_vals in self.q.items():
            best_idx = int(np.argmax(q_vals))
            rows.append({
                "state":      state,
                "best_delta": self.DELTAS[best_idx],
                "q_value":    round(q_vals[best_idx], 3),
            })
        return pd.DataFrame(rows).sort_values("state")


# ─────────────────────────────────────────────────
# 4. EVENT WATCHER
# ─────────────────────────────────────────────────

# Venues near Inglewood/USC to monitor
TARGET_VENUES = {
    "Crypto.Arena":       {"lat": 34.0430, "lon": -118.2673, "capacity": 19_000, "zone": "downtown"},
    "SoFi Stadium":       {"lat": 33.9535, "lon": -118.3392, "capacity": 70_240, "zone": "inglewood"},
    "BMO Stadium":        {"lat": 34.0122, "lon": -118.2842, "capacity": 22_000, "zone": "downtown"},
    "Banc of California": {"lat": 34.0122, "lon": -118.2842, "capacity": 22_000, "zone": "downtown"},
    "USC Galen Center":   {"lat": 34.0227, "lon": -118.2856, "capacity": 10_258, "zone": "USC"},
    "Hollywood Bowl":     {"lat": 34.1122, "lon": -118.3390, "capacity": 17_500, "zone": "hollywood"},
}

DEMAND_THRESHOLDS = {
    "high":   0.7,   # send strong alert
    "medium": 0.4,   # send soft suggestion
}


def score_event(capacity: int, hours_until: float) -> float:
    """
    0–1 demand score.  Peaks 1–3 hours before a big event.
    """
    if hours_until > 48 or hours_until < 0:
        return 0.0
    size_score  = min(capacity / 70_000, 1.0)
    # urgency curve: max at 2 hrs out, decays sharply after start
    if hours_until > 0:
        urgency = np.exp(-0.5 * ((hours_until - 2) / 3) ** 2)
    else:
        urgency = max(0, 1 + hours_until / 2)  # fades during event
    return round(float(size_score * urgency), 3)


def fetch_upcoming_events(api_key: str | None = None) -> list[dict]:
    """
    Call Ticketmaster Discovery API for events near Inglewood.
    Falls back to realistic mock data if no key is provided.
    """
    if api_key:
        try:
            import requests
            url = "https://app.ticketmaster.com/discovery/v2/events.json"
            params = {
                "apikey":      api_key,
                "latlong":     "33.9535,-118.3392",
                "radius":      "10",
                "unit":        "miles",
                "size":        "20",
                "classificationName": "music,sports",
            }
            r = requests.get(url, params=params, timeout=8)
            r.raise_for_status()
            raw = r.json()
            events = []
            for e in raw.get("_embedded", {}).get("events", []):
                try:
                    dt_str   = e["dates"]["start"].get("dateTime", "")
                    dt       = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    hours    = (dt - datetime.now(dt.tzinfo)).total_seconds() / 3600
                    venue    = e.get("_embedded", {}).get("venues", [{}])[0]
                    capacity = int(venue.get("generalInfo", {}).get("generalRule", "10000").split()[0]
                                   if venue else 15_000)
                    events.append({
                        "name":     e.get("name", "Event"),
                        "venue":    venue.get("name", "Unknown"),
                        "hours_until": round(hours, 1),
                        "capacity": capacity,
                        "demand_score": score_event(capacity, hours),
                    })
                except Exception:
                    continue
            return events
        except Exception as exc:
            print(f"[EventWatcher] API call failed ({exc}), using mock data.")

    # ── Mock events (always available for demo) ─────
    now = datetime.now()
    return [
        {
            "name":        "Lakers vs. Warriors",
            "venue":       "Crypto.Arena",
            "hours_until": 3.5,
            "capacity":    19_000,
            "demand_score": score_event(19_000, 3.5),
        },
        {
            "name":        "Taylor Swift | Eras Tour",
            "venue":       "SoFi Stadium",
            "hours_until": 18.0,
            "capacity":    70_240,
            "demand_score": score_event(70_240, 18.0),
        },
        {
            "name":        "USC vs. UCLA Football",
            "venue":       "SoFi Stadium",
            "hours_until": 36.0,
            "capacity":    70_240,
            "demand_score": score_event(70_240, 36.0),
        },
        {
            "name":        "Bad Bunny",
            "venue":       "Crypto.Arena",
            "hours_until": 72.0,
            "capacity":    19_000,
            "demand_score": score_event(19_000, 72.0),
        },
    ]


def homeowner_alerts(events: list[dict]) -> list[dict]:
    """Return notification payloads for events above threshold."""
    alerts = []
    for ev in events:
        ds = ev["demand_score"]
        if ds >= DEMAND_THRESHOLDS["high"]:
            level   = "high"
            message = (
                f"🔥 High demand! {ev['name']} at {ev['venue']} is "
                f"{ev['hours_until']:.0f} hrs away. List your spot now — "
                f"you could earn significantly more than usual."
            )
        elif ds >= DEMAND_THRESHOLDS["medium"]:
            level   = "medium"
            message = (
                f"📍 {ev['name']} at {ev['venue']} in "
                f"{ev['hours_until']:.0f} hrs. Consider listing your spot."
            )
        else:
            continue
        alerts.append({**ev, "alert_level": level, "message": message})
    return alerts


# ─────────────────────────────────────────────────
# 5. UNIFIED PRICING API
# ─────────────────────────────────────────────────

class ParkSharePricer:
    """
    Single entry point for the Streamlit app and future backend.

    Usage:
        pricer = ParkSharePricer()
        result = pricer.price(
            zone="inglewood",
            active_users=320,
            listed_spots=12,
            hours_to_event=2.5,
            event_size=0.8,
            day_of_week=5,
            hour=18,
            temperature=72,
        )
        # result = {"base": 2.12, "surge_mult": 2.1, "final": 4.46, "rl_delta": 0.15}
    """

    def __init__(self, model_dir: str = "."):
        os.makedirs(model_dir, exist_ok=True)
        self.surge_model = SurgeModel(f"{model_dir}/surge_model.pkl")
        self.rl          = RLFeedbackLoop(f"{model_dir}/qtable.json")
        self.history: list[dict] = []

    def price(
        self,
        zone:           str   = "inglewood",
        active_users:   int   = 50,
        listed_spots:   int   = 20,
        hours_to_event: float = 999,
        event_size:     float = 0.0,
        day_of_week:    int   = 2,
        hour:           int   = 14,
        temperature:    float = 72,
    ) -> dict:
        b = base_price(zone)
        features = {
            "active_users":   active_users,
            "listed_spots":   listed_spots,
            "hours_to_event": hours_to_event,
            "event_size":     event_size,
            "day_of_week":    day_of_week,
            "hour":           hour,
            "is_weekend":     int(day_of_week >= 5),
            "temperature":    temperature,
        }
        raw_mult     = self.surge_model.predict(features)
        demand_ratio = active_users / max(listed_spots, 1)
        rl_delta     = self.rl.choose_delta(demand_ratio, hours_to_event)
        final_mult   = round(np.clip(raw_mult + rl_delta, 1.0, 3.5), 3)
        final_price  = round(np.clip(b * final_mult, FLOOR_PRICE, CEILING_PRICE), 2)

        record = {
            "timestamp":      datetime.now().isoformat(),
            "zone":           zone,
            "base":           b,
            "surge_mult":     final_mult,
            "rl_delta":       rl_delta,
            "final_price":    final_price,
            "demand_ratio":   round(demand_ratio, 2),
            "hours_to_event": hours_to_event,
            **features,
        }
        self.history.append(record)
        return record

    def record_outcome(self, booking_completed: bool, revenue: float):
        """
        Call after a parking session ends to feed the RL loop.
        In production this fires from a webhook when checkout occurs.
        """
        if not self.history:
            return
        last = self.history[-1]
        self.rl.update(
            demand_ratio      = last["demand_ratio"],
            hours_to_event    = last["hours_to_event"],
            delta_used        = last["rl_delta"],
            booking_completed = booking_completed,
            revenue           = revenue,
        )

    def simulate_rl_training(self, n: int = 200):
        """
        Simulate n booking outcomes to pre-warm the RL table.
        Useful for demo / cold-start.
        """
        rng = np.random.default_rng(0)
        new_rows = []
        for _ in range(n):
            dr  = float(rng.uniform(0.2, 10))
            hte = float(rng.choice([999] * 5 + list(rng.uniform(0, 12, 3))))
            delta = self.rl.choose_delta(dr, hte)
            # synthetic: high demand + event → more likely booking
            p_book = min(0.9, 0.3 + 0.06 * dr + (0.4 if hte < 6 else 0))
            booked = bool(rng.random() < p_book)
            rev    = float(rng.uniform(5, 40)) if booked else 0.0
            self.rl.update(dr, hte, delta, booked, rev)
            # also collect rows for surge model retraining
            new_rows.append({
                "active_users":    int(dr * 15),
                "listed_spots":    15,
                "hours_to_event":  hte,
                "event_size":      float(rng.uniform(0, 1)) if hte < 12 else 0,
                "day_of_week":     int(rng.integers(0, 7)),
                "hour":            int(rng.integers(6, 23)),
                "is_weekend":      int(rng.integers(0, 7) >= 5),
                "temperature":     float(rng.uniform(55, 95)),
                "surge_multiplier": float(np.clip(1 + 0.3 * dr + (0.5 if hte < 4 else 0), 1, 3.5)),
            })
        self.surge_model.retrain(pd.DataFrame(new_rows))
        print(f"[ParkSharePricer] RL warm-up complete ({n} simulated bookings).")
