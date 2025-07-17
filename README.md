# 🔐 TON Wallet Tracker

A real-time wallet tracking system for the **TON blockchain**, built with **Python**, **Redis**, and the **TON API**. It monitors wallet transactions, traces, and mempool activity, then delivers instant updates to a **Telegram bot** using Redis Pub/Sub.

---

## What It Does

* 📲 Tracks specific TON wallet addresses.
* 🌍 Supports **global tracking** of all TON network activity.
* 🧠 Detects and publishes:

  * ✅ **Transactions**
  * 🔍 **Execution traces**
  * 🕒 **Mempool entries**
* 🧵 Uses **multi-threaded SSE listeners** to ensure high reliability.
* 💬 Sends updates to users via a **Telegram bot**.

---

## ⚙️ Architecture Overview

```
User ↔ Telegram Bot
           ↓
      Redis Pub/Sub
           ↓
TON API (SSE Streams)
```

* Telegram bot handles user commands and subscriptions.
* Redis stores active streams and publishes updates.
* SSEClient connects to TON API and forwards updates.

---

## 🛠 Tech Stack

* **Python**
* **Redis**
* **Telebot** (Telegram Bot API wrapper)
* **SSEClient**
* **tonapi.io** (TON public API)

---

## 🔧 Setup

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Environment setup**

   Create a `.env` file:

   ```env
    TG_API_TOKEN=<your_tg_bot_token>
    TRACKER_API_BASE=<url_of_hosted_backend>
    REDIS_HOST=<your_redis_host>
    REDIS_PORT=6379
    REDIS_DB=0
   ```

3. **Run Redis**

   ```bash
   redis-server
   ```

4. **Start the event backend**

   ```bash
   python ton_tracker.py
   ```

5. **Start the Telegram bot**

   ```bash
   python ton_bot.py
   ```

---

## 💬 Telegram Bot Commands

| Command              | Action                                   |
| -------------------- | ---------------------------------------- |
| `/start`             | Start the bot and see menu               |
| `/follow <wallet>`   | Track a specific wallet                  |
| `/unfollow <wallet>` | Stop tracking a specific wallet          |
| `/mywallets`         | Show currently tracked wallets           |
| `/clearwallets`      | Remove all followed wallets              |
| `/followall`         | Subscribe to all blockchain events       |
| `/unfollowall`       | Unsubscribe from all blockchain activity |

---

## 📡 Redis Channels Used

* `ton_tx_channel` → Transaction alerts
* `ton_trace_channel` → Execution trace logs
* `ton_mempool_channel` → Pending mempool entries
* `tracked_wallets` → Set of all active wallet streams
* `user:<chat_id>:wallets` → Wallets tracked per user
* `global_subscribers` → Users subscribed to ALL events

---

## 📄 Example Use Case

1. User starts the bot via Telegram.
2. Sends `/follow EQCabc...` to track a wallet.
3. The backend adds that wallet to `tracked_wallets`.
4. SSE stream for that wallet starts if not active.
5. Any transaction/mempool/trace updates for that wallet are broadcast via Redis.
6. Bot sends alerts directly to subscribed users.

---

## 📜 License

MIT
