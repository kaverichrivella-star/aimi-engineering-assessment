# AI/ML Stock Screener (Streamlit)

This scaffold provides a Streamlit-based starter for the Assignment 1 screening application. It includes:

- Modular data provider adapters (Mock, placeholders for Fyers/AngelOne).
- Indicator calculations (SMMA) and crossover detection.
- A mock real-time dashboard to demonstrate layout and flows.

Setup

1. Create a Python virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. To run the demo (uses mock data):

```bash
streamlit run src/app.py
```

Notes

- Replace or implement the `FyersProvider` / `AngelProvider` in `src/providers.py` with real API calls and credentials.
- The mock provider simulates trade quantities, prices and depth for development.
- Packaging to `.exe` can be done with `pyinstaller` once credentials and live adapters are implemented.

Broker Integration
------------------

This scaffold includes adapter skeletons for both brokers under `src/adapters/`:

- `src/adapters/fyers_adapter.py` — Fyers adapter skeleton with method stubs.
- `src/adapters/angel_adapter.py` — Angel One adapter skeleton with method stubs.

To enable a live broker adapter:

1. Copy `.env.example` to `.env` and fill your keys.
2. Update `src/config.py` if you prefer another configuration mechanism.
3. Implement the HTTP calls in the adapter methods (see inline comments).
3. In `src/app.py` select `Fyers` or `Angel` from the provider dropdown. The app will attempt to fetch an NSE symbol list from the configured instrument map endpoint and fall back to the local `symbols.csv` list if needed.

If you want to add real symbols for a live broker integration, set:

- `FYERS_INSTRUMENT_MAP_ENDPOINT`
- `ANGEL_INSTRUMENT_MAP_ENDPOINT`

The adapter will use those endpoints to fetch symbols compatible with the broker API.


Provider selection
------------------

The Streamlit app sidebar allows selecting the data provider: `Mock`, `Fyers`, or `Angel`.
Set credentials in `.env` and choose the provider; the app will attempt to call the adapter endpoints. See `INTEGRATION_CHECKLIST.md` for step-by-step tests.

Security
--------

- Do NOT commit your `.env` or credentials. Use `.gitignore` to exclude them.
- Mask or remove any API keys before sharing code or recordings.

Training the ML predictor
-------------------------

To train a synthetic model (demo only):

```bash
python src/train_predictor.py
```

This will produce `models/model.joblib`. The app will load this model automatically if present.

Running tests
-------------

Run the unit tests with:

```bash
pytest -q
```

Building a single executable (Windows PowerShell)
-----------------------------------------------

Run:

```powershell
.\build_exe.ps1
```

Demo recording
--------------

Record your screen using `ffmpeg` (install separately). Example command for Windows:

```powershell
ffmpeg -f gdigrab -framerate 15 -offset_x 0 -offset_y 0 -video_size 1920x1080 -i desktop -codec:v libx264 -preset ultrafast demo.mp4
```

Remember to mask or remove credentials from the UI before recording.