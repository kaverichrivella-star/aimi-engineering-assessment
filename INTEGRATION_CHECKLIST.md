Integration Checklist — Broker Adapter

1. Add credentials to `.env` (do NOT commit):

   - For Fyers: `FYERS_API_KEY`, `FYERS_ACCESS_TOKEN`, `FYERS_INSTRUMENT_MAP_ENDPOINT`.
   - For Angel One: `ANGEL_API_KEY`, `ANGEL_CLIENT_ID`, `ANGEL_INSTRUMENT_MAP_ENDPOINT`.

2. Confirm `src/config.py` loads your env vars. If needed, set them manually in the environment.

3. Start the Streamlit app and select `Fyers` or `Angel` from the provider dropdown.

4. Validate provider status in the UI message:
   - If live credentials are missing, the app uses Yahoo fallback data.
   - If live broker data is available, the provider should return quoted symbols.

5. Verify symbol feed:
   - `get_symbols()` returns NSE symbols.
   - Instrument list should include `RELIANCE`, `TCS`, `INFY`, or other NSE tickers.

6. Verify pricing and liquidity endpoints:
   - `get_latest(symbol)` returns `{'symbol', 'ltp'}`.
   - `get_depth(symbol)` returns `bid_price`, `ask_price`, `bid_qty`, and `ask_qty`.

7. Verify history endpoints:
   - `get_history(symbol, minutes)` works for 5, 20, 60, and 120.
   - Returned bars should include timestamp, price, and volume.

8. Test the app filters:
   - Loosen `Min LTP`, `Min Bid Qty`, `Min Ask Qty`, and ETQ thresholds if no symbols pass.
   - Use the `Show reasoning` toggle to inspect AI explanations.

9. Review P/L tracking:
   - Confirm open positions appear in the dashboard.
   - Confirm realized and unrealized P/L update as new signals arrive.

10. Optional:
   - Use `python src/train_predictor.py` to train a fresh model from historical data.
   - Build the executable with `.uild_exe.ps1`.
