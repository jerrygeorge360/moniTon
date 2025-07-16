import os
import time
import threading
import json
import sseclient
import redis
from dotenv import load_dotenv
load_dotenv()

TON_API_TOKEN = os.getenv('TON_API_TOKEN')
BASE_URL = os.getenv('TON_API_BASE', 'https://tonapi.io')
headers = {"Authorization": f"Bearer {TON_API_TOKEN}"}

redis_url = os.getenv("REDIS_URL")
if redis_url:
    # Connect using the full URL, e.g. Upstash URL with TLS and password
    redis_client = redis.from_url(redis_url)
else:
    # Connect using individual env vars with defaults if not set
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_db = int(os.getenv("REDIS_DB", 0))
    redis_password = os.getenv("REDIS_PASSWORD", None)

    redis_client = redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        password=redis_password,
    )

active_streams = set()

# ==== SSE GENERIC WRAPPER WITH RESILIENCE ====
def stream_sse_events(url: str, label: str, handler_fn):
    while True:
        print(f"🛰️  [{label}] Connecting to: {url}")
        try:
            client = sseclient.SSEClient(url, headers=headers)
            for event in client:
                if event.event == "message" and event.data.strip():
                    try:
                        handler_fn(json.loads(event.data))
                    except Exception as e:
                        print(f"❌ [{label}] Error parsing message:", e)
        except Exception as e:
            print(f"❌ [{label}] SSE connection error: {e}")
        print(f"🔁 [{label}] Reconnecting in 5 seconds...\n")
        time.sleep(5)

# ==== EVENT HANDLERS ====
def handle_tx_event(data):
    account = data.get("account_id")
    tx_hash = data.get("tx_hash")
    lt = data.get("lt")
    actions = data.get("actions", [])

    md = f"*✅ New Transaction on Mainnet*\n"
    md += f"`Account:` `{account}`\n"
    md += f"`Tx Hash:` `{tx_hash}`\n"
    md += f"`Lt:` `{lt}`\n"

    if actions:
        md += "*Actions:*\n"
        for action in actions:
            act_type = action.get("type", "Unknown")
            amount = action.get("amount", "N/A")
            md += f"• `{act_type}` — `{amount}`\n"

    redis_client.publish("ton_tx_channel", md)

def handle_trace_event(data):
    trace_hash = data.get("hash")
    involved = data.get("accounts", [])
    md = f"*🔍 Trace Event*\n"
    md += f"`Hash:` `{trace_hash}`\n"
    md += f"`Accounts:` `{', '.join(involved)}`"
    redis_client.publish("ton_trace_channel", md)

def handle_mempool_event(data):
    involved = data.get("involved_accounts", [])
    md = f"*🕒 Mempool Tx Detected*\n"
    md += f"`Accounts:` `{', '.join(involved)}`"
    redis_client.publish("ton_mempool_channel", md)

# ==== STREAM PER WALLET ====
def stream_wallet_transactions(wallet):
    url = f"{BASE_URL}/v2/sse/accounts/transactions?accounts={wallet}"
    stream_sse_events(url, f"TX-{wallet}", handle_tx_event)

def stream_wallet_traces(wallet):
    url = f"{BASE_URL}/v2/sse/accounts/traces?accounts={wallet}"
    stream_sse_events(url, f"TRACE-{wallet}", handle_trace_event)

def stream_wallet_mempool(wallet):
    url = f"{BASE_URL}/v2/sse/mempool?accounts={wallet}"
    stream_sse_events(url, f"MEMPOOL-{wallet}", handle_mempool_event)

# ==== REDIS TRACKER ====
def listen_for_tracked_wallets():
    print("🔁 Monitoring Redis for new wallets...")
    while True:
        try:
            wallets = redis_client.smembers("tracked_wallets")
            for wallet_bytes in wallets:
                wallet = wallet_bytes.decode()
                if wallet not in active_streams:
                    print(f"🆕 Tracking wallet: {wallet}")
                    threading.Thread(target=stream_wallet_transactions, args=(wallet,), daemon=True).start()
                    threading.Thread(target=stream_wallet_traces, args=(wallet,), daemon=True).start()
                    threading.Thread(target=stream_wallet_mempool, args=(wallet,), daemon=True).start()
                    active_streams.add(wallet)
        except Exception as e:
            print("❌ Error checking tracked_wallets:", e)
        time.sleep(3)

# ==== GLOBAL LISTENERS ====
def listen_global_transactions():
    url = f"{BASE_URL}/v2/sse/accounts/transactions?accounts=ALL"
    threading.Thread(target=stream_sse_events, args=(url, "TX-ALL", handle_tx_event), daemon=True).start()

def listen_global_traces():
    url = f"{BASE_URL}/v2/sse/accounts/traces?accounts=ALL"
    threading.Thread(target=stream_sse_events, args=(url, "TRACE-ALL", handle_trace_event), daemon=True).start()

def listen_global_mempool():
    url = f"{BASE_URL}/v2/sse/mempool?accounts=ALL"
    threading.Thread(target=stream_sse_events, args=(url, "MEMPOOL-ALL", handle_mempool_event), daemon=True).start()

# ==== MAIN ====
if __name__ == "__main__":
    print("TON Tracker Backend Started")
    listen_global_transactions()
    listen_global_traces()
    listen_global_mempool()
    listen_for_tracked_wallets()
    while True:
        time.sleep(1)
