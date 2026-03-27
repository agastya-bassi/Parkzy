# Parkzy — Dynamic Parking Pricing Engine

Airbnb for parking spots near Inglewood / USC. Homeowners list their driveways and the ML engine prices them dynamically based on demand, events, and real-time app activity.

## How it works

Base price anchored to LA meter averages (always 15% cheaper to stay competitive). A gradient boosted model predicts a surge multiplier based on active users, supply/demand ratio, and proximity to nearby events. A reinforcement learning layer sits on top and self-improves from real booking outcomes over time. Event APIs (Ticketmaster) trigger push alerts to homeowners when a concert or game is coming up nearby.

## Setup
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Structure

- `pricing_engine.py` — ML pricing logic (base model, surge model, RL loop, event watcher)
- `app.py` — Streamlit demo app

## Notes

- Add a Ticketmaster API key in the Events tab for live event data (free at developer.ticketmaster.com)
- Model checkpoints (`*.pkl`, `qtable.json`) are gitignored — they regenerate on first run