import json
import os
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

    # Telegram bot token
API_TOKEN = '7629442630:AAEXnWK1NaSAsNjIpy_NQ2AMCBG9wu6vCS4'

    # JSON dosyaları
TRACKED_FILE = "tracked_tickers.json"
PURCHASED_FILE = "purchased_tickers.json"

    # Verileri saklamak için global değişkenler
tracked_tickers = {}
purchased_tickers = {}

    # JSON dosyasından verileri yükleme
def load_data():
        global tracked_tickers, purchased_tickers
        if os.path.exists(TRACKED_FILE):
            with open(TRACKED_FILE, 'r') as f:
                tracked_tickers = json.load(f)
        if os.path.exists(PURCHASED_FILE):
            with open(PURCHASED_FILE, 'r') as f:
                purchased_tickers = json.load(f)

    # Verileri JSON dosyasına kaydetme
def save_data():
        with open(TRACKED_FILE, 'w') as f:
            json.dump(tracked_tickers, f, indent=4)
        with open(PURCHASED_FILE, 'w') as f:
            json.dump(purchased_tickers, f, indent=4)

    # Binance ve Bitget API'den fiyat alma
async def fetch_price(symbol):
        binance_url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        bitget_url = f"https://api.bitget.com/api/v2/spot/market/tickers?symbol={symbol}"

        try:
            # Binance API'den fiyat al
            async with aiohttp.ClientSession() as session:
                async with session.get(binance_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return float(data['price'])
                    else:
                        print(f"Binance API Hatası: {response.status}, Mesaj: {await response.text()}")
        except Exception as e:
            print(f"Binance API Hatası: {e}")

        # Binance başarısız olursa Bitget API'ye geç
        try:
            print("Binance API'den cevap alınamadı, Bitget API'ye geçiliyor...")
            async with aiohttp.ClientSession() as session:
                async with session.get(bitget_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data["code"] == "00000":
                            if isinstance(data["data"], list) and data["data"]:
                                for ticker in data["data"]:
                                    if ticker["symbol"] == symbol:
                                        return float(ticker["lastPr"])
                                print(f"{symbol} Bitget API'de bulunamadı.")
                                return None
                            else:
                                print("Bitget API'den gelen 'data' anahtarında liste bulunamadı.")
                                return None
                        else:
                            print(f"Bitget API Hatası: {data['msg']}")
                            return None
                    else:
                        print(f"Bitget API Hatası: {response.status}, Mesaj: {await response.text()}")
                        return None
        except Exception as e:
            print(f"Bitget API Bağlantı Hatası: {e}")
            return None

    # Ticker ekleme komutu
async def add_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) != 3:
                await update.message.reply_text("Lütfen şu formatta komut gönderin: /add TICKER BAŞLANGIÇ_FİYAT YÜZDE")
                return

            ticker, start_price, percentage = context.args
            start_price = float(start_price)
            percentage = float(percentage)

            tracked_tickers[ticker.upper()] = {'start_price': start_price, 'percentage': percentage}
            save_data()  # Verileri kaydet
            await update.message.reply_text(f"{ticker.upper()} {start_price} fiyatı ve % {percentage} değişimle takip ediliyor.")
        except ValueError:
            await update.message.reply_text("Lütfen geçerli bir fiyat ve yüzde değeri girin.")
        except Exception as e:
            await update.message.reply_text(f"Hata: {e}")

    # Ticker satın alma komutu
async def buy_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) != 3:
                await update.message.reply_text("Lütfen şu formatta komut gönderin: /buy TICKER ALIŞ_FİYATI MİKTAR")
                return

            ticker, buy_price, amount = context.args
            buy_price = float(buy_price)
            amount = float(amount)

            purchased_tickers[ticker.upper()] = {'buy_price': buy_price, 'amount': amount}
            save_data()  # Verileri kaydet
            await update.message.reply_text(f"{ticker.upper()} {buy_price} fiyatıyla {amount} miktarında eklendi.")
        except ValueError:
            await update.message.reply_text("Lütfen geçerli bir fiyat ve miktar girin.")
        except Exception as e:
            await update.message.reply_text(f"Hata: {e}")

    # Kar/Zarar komutu
async def profit_loss(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not purchased_tickers:
            await update.message.reply_text("Şu anda satın alınmış bir ticker yok.")
            return

        total_profit_loss = 0
        message = "Kar/Zarar Durumu:\n"
        for ticker, info in purchased_tickers.items():
            current_price = await fetch_price(ticker)
            if current_price is not None:
                buy_price = info['buy_price']
                amount = info['amount']
                profit_loss = (current_price - buy_price) * amount
                total_profit_loss += profit_loss
                message += f"- {ticker}: Alış {buy_price}, Şu Anki {current_price}, Kar/Zarar: {profit_loss:.2f} USD\n"
            else:
                message += f"- {ticker}: Fiyat bilgisi alınamadı.\n"

        message += f"\nToplam Kar/Zarar: {total_profit_loss:.2f} USD"
        await update.message.reply_text(message)

    # Ticker listesini gösterme komutu
async def list_tickers(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not tracked_tickers:
            await update.message.reply_text("Şu anda takip edilen bir ticker yok.")
        else:
            message = "Takip edilen ticker'lar:\n"
            for ticker, info in tracked_tickers.items():
                message += f"- {ticker}: {info['start_price']} USD, % {info['percentage']} değişim\n"
            await update.message.reply_text(message)

    # Ticker silme komutu
async def remove_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if len(context.args) != 1:
                await update.message.reply_text("Lütfen şu formatta komut gönderin: /remove TICKER")
                return

            ticker = context.args[0].upper()
            if ticker in tracked_tickers:
                del tracked_tickers[ticker]
                save_data()  # Verileri kaydet
                await update.message.reply_text(f"{ticker} takip listesinden çıkarıldı.")
            else:
                await update.message.reply_text(f"{ticker} takip listesinde bulunamadı.")
        except Exception as e:
            await update.message.reply_text(f"Hata: {e}")

    # Fiyat sorgulama komutu
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if not context.args:
                await update.message.reply_text("Lütfen bir sembol girin. Örnek: /price BTCUSDT")
                return

            symbol = context.args[0].upper()
            price = await fetch_price(symbol)
            if price is not None:
                await update.message.reply_text(f"{symbol} fiyatı: {price} USD")
            else:
                await update.message.reply_text(f"{symbol}: Fiyat bilgisi alınamadı.")
        except Exception as e:
            await update.message.reply_text(f"Bir hata oluştu: {e}")

    # Botu çalıştırma
def main():
        load_data()  # Verileri yükle
        application = Application.builder().token(API_TOKEN).build()

        application.add_handler(CommandHandler("add", add_ticker))
        application.add_handler(CommandHandler("list", list_tickers))
        application.add_handler(CommandHandler("remove", remove_ticker))
        application.add_handler(CommandHandler("buy", buy_ticker))
        application.add_handler(CommandHandler("profit", profit_loss))
        application.add_handler(CommandHandler("price", price_command))

        application.run_polling()

if __name__ == "__main__":
        main()
