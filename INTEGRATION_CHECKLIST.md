Integration Checklist — Broker Adapter

1. Add credentials to `.env` (do NOT commit):

   - For Fyers: `FYERS_API_KEY`, `FYERS_ACCESS_TOKEN`, optionally `FYERS_INSTRUMENTS_ENDPOINT`.
   - For Angel One: `ANGEL_API_KEY`, `ANGEL_CLIENT_ID`, optionally `ANGEL_INSTRUMENTS_ENDPOINT`.

2. Configure `src/config.py` (or set env vars).

3. Start the Streamlit app and select provider from the sidebar.

4. Verify `get_symbols()` returns NSE symbols. If using a custom instrument map endpoint, ensure it returns JSON array with `symbol` or `tradingsymbol`.

5. Test `get_latest(symbol)` for a few symbols and confirm returned `ltp` is numeric.

6. Test `get_depth(symbol)` and confirm `bid_price`, `ask_price`, `bid_qty`, `ask_qty` are present.

7. Test `get_history(symbol, minutes)` for 5/20/60 and verify time ordering and price/qty values.

8. Monitor rate limits and adjust `refresh (s)` in UI.

9. If available, consider switching to WebSocket/streaming endpoint for lower-latency updates.
