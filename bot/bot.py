import os
import redis
import telebot
from telebot import types
import threading
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TG_API_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)


redis_url = os.getenv("REDIS_URL")
if redis_url:
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



# === Redis Helpers ===
def get_user_wallets(chat_id):
    return {w.decode() for w in redis_client.smembers(f"user:{chat_id}:wallets")}


def add_wallet_for_user(chat_id, wallet):
    redis_client.sadd("tracked_wallets", wallet)
    redis_client.sadd(f"user:{chat_id}:wallets", wallet)
    redis_client.sadd(f"wallet:{wallet}:subscribers", chat_id)


def remove_wallet_for_user(chat_id, wallet):
    redis_client.srem(f"user:{chat_id}:wallets", wallet)
    redis_client.srem(f"wallet:{wallet}:subscribers", chat_id)


def get_wallet_subscribers(wallet):
    return {int(uid.decode()) for uid in redis_client.smembers(f"wallet:{wallet}:subscribers")}


def clear_wallets_for_user(chat_id):
    wallets = get_user_wallets(chat_id)
    for wallet in wallets:
        remove_wallet_for_user(chat_id, wallet)


def add_global_subscriber(chat_id):
    redis_client.sadd("global_subscribers", chat_id)


def remove_global_subscriber(chat_id):
    redis_client.srem("global_subscribers", chat_id)


def is_global_subscriber(chat_id):
    return redis_client.sismember("global_subscribers", chat_id)


# === Commands ===
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        types.KeyboardButton("➕ Follow Wallet"),
        types.KeyboardButton("➖ Unfollow Wallet"),
        types.KeyboardButton("🌐 Follow All"),
        types.KeyboardButton("🚫 Unfollow All"),
        types.KeyboardButton("📋 My Wallets"),
        types.KeyboardButton("🧹 Clear Wallets"),
        types.KeyboardButton("📖 Help")
    )
    bot.send_message(
        chat_id,
        "👋 *Welcome to TON Wallet Tracker Bot!*\n\n"
        "📡 Track *TON wallets* in real time for:\n"
        "• Transactions\n"
        "• Trace Events\n"
        "• Mempool Activity\n\n"
        "🔽 Choose an action from the buttons below!",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


@bot.message_handler(func=lambda msg: msg.text == "📖 Help" or msg.text == "/help")
def handle_help(message):
    help_text = (
        "*📖 Help Guide:*\n\n"
        "`/follow <wallet>` — Track a specific wallet\n"
        "`/unfollow <wallet>` — Unfollow a wallet\n"
        "`/followall` — Track ALL wallets globally\n"
        "`/unfollowall` — Stop tracking all\n"
        "`/mywallets` — View your tracking list\n"
        "`/clearwallets` — Clear your wallet list"
    )
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")


@bot.message_handler(commands=['follow'])
def handle_follow(message):
    parts = message.text.split()
    if len(parts) != 2:
        bot.send_message(message.chat.id, "❌ Usage: `/follow <wallet_address>`", parse_mode="Markdown")
        return
    wallet = parts[1].strip()
    if not wallet.startswith("E") and not wallet.startswith("U"):
        bot.send_message(message.chat.id, "❌ Invalid wallet format. Wallet must start with `E...` or `U...`",
                         parse_mode="Markdown")

        return
    add_wallet_for_user(message.chat.id, wallet)
    bot.send_message(
        message.chat.id,
        f"✅ Now tracking `{wallet}` for:\n"
        "• Transactions\n• Traces\n• Mempool",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=['unfollow'])
def handle_unfollow(message):
    parts = message.text.split()
    if len(parts) != 2:
        bot.send_message(message.chat.id, "❌ Usage: `/unfollow <wallet_address>`", parse_mode="Markdown")
        return
    wallet = parts[1].strip()
    remove_wallet_for_user(message.chat.id, wallet)
    bot.send_message(message.chat.id, f"🔕 Unfollowed `{wallet}`", parse_mode="Markdown")


@bot.message_handler(commands=['mywallets'])
def handle_mywallets(message):
    wallets = get_user_wallets(message.chat.id)
    is_global = is_global_subscriber(message.chat.id)
    if not wallets and not is_global:
        bot.send_message(message.chat.id, "📭 You are not tracking any wallets.")
        return
    msg = "🧾 *Your Tracking List:*\n"
    if wallets:
        msg += "\n👛 *Wallets:*\n"
        for w in wallets:
            msg += f"• `{w}`\n"
    if is_global:
        msg += "\n🌍 You are tracking *ALL* global events."
    bot.send_message(message.chat.id, msg, parse_mode="Markdown")



@bot.message_handler(commands=['clearwallets'])
def handle_clearwallets(message):
    clear_wallets_for_user(message.chat.id)
    bot.send_message(message.chat.id, "🧹 All wallets cleared from your list.")


@bot.message_handler(commands=['followall'])
def handle_followall(message):
    add_global_subscriber(message.chat.id)
    bot.send_message(message.chat.id, "📡 Subscribed to *ALL global wallet events*.", parse_mode="Markdown")


@bot.message_handler(commands=['unfollowall'])
def handle_unfollowall(message):
    remove_global_subscriber(message.chat.id)
    bot.send_message(message.chat.id, "🔕 Unsubscribed from *ALL global wallet events*.", parse_mode="Markdown")


# === Redis Event Broadcaster ===
def redis_listener():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("ton_tx_channel", "ton_trace_channel", "ton_mempool_channel")
    print("📡 Listening to Redis pubsub...")
    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                md_msg = message['data'].decode()
                target_account = None
                for line in md_msg.splitlines():
                    if "`Account:`" in line:
                        target_account = line.split("`")[3]
                        break
                sent_to = set()
                if target_account:
                    for uid in get_wallet_subscribers(target_account):
                        bot.send_message(uid, md_msg, parse_mode="Markdown")
                        sent_to.add(uid)
                for chat_id in redis_client.smembers("global_subscribers"):
                    uid = int(chat_id.decode())
                    if uid not in sent_to:
                        bot.send_message(uid, md_msg, parse_mode="Markdown")
            except Exception as e:
                print("❌ Redis message send error:", e)


if __name__ == "__main__":
    # Start the bot polling (blocking)
    print("TON Bot Running...")
    redis_thread = threading.Thread(target=redis_listener, daemon=True)
    redis_thread.start()
    bot.infinity_polling()
