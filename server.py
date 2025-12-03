from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/public/c2c/adv/search"


def fetch_binance_p2p_price(trade_type="BUY", fiat="VND", rows=10):
    """
    Gọi Binance P2P, lấy danh sách offer, trả về giá trung bình.
    trade_type: "BUY" hoặc "SELL"
    fiat: "VND", "USD", ...
    rows: số offer muốn lấy (tối đa ~10–20)
    """
    payload = {
        "page": 1,
        "rows": rows,
        "asset": "USDT",
        "tradeType": trade_type,
        "fiat": fiat,
        "publisherType": None
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://p2p.binance.com",
        "Referer": "https://p2p.binance.com/en"
    }

    try:
        resp = requests.post(
            BINANCE_P2P_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
    except requests.RequestException as e:
        # Lỗi mạng, timeout, v.v.
        return None, {"error": "network_error", "detail": str(e)}

    if resp.status_code != 200:
        return None, {
            "error": "binance_http_error",
            "status_code": resp.status_code,
            "body": resp.text[:500],
        }

    try:
        data = resp.json()
    except ValueError:
        return None, {
            "error": "binance_json_error",
            "body": resp.text[:500],
        }

    if not data or "data" not in data or not data["data"]:
        return None, {"error": "no_offers"}

    prices = []
    for item in data["data"]:
        try:
            price_str = item["adv"]["price"]
            price = float(price_str)
            prices.append(price)
        except (KeyError, ValueError, TypeError):
            continue

    if not prices:
        return None, {"error": "no_valid_prices"}

    avg_price = sum(prices) / len(prices)
    return avg_price, None


@app.route("/usdt_p2p_price", methods=["GET"])
def usdt_p2p_price():
    """
    Endpoint: /usdt_p2p_price?tradeType=BUY&fiat=VND&rows=10

    Trả về JSON:
    {
      "price": 25300.12,
      "tradeType": "BUY",
      "fiat": "VND",
      "rows": 10,
      "source": "binance_p2p"
    }
    """
    trade_type = request.args.get("tradeType", "BUY").upper()
    fiat = request.args.get("fiat", "VND").upper()
    rows_param = request.args.get("rows", "10")

    try:
        rows = int(rows_param)
    except ValueError:
        rows = 10

    rows = max(1, min(rows, 20))  # giới hạn cho an toàn

    price, error = fetch_binance_p2p_price(trade_type, fiat, rows)

    if error is not None or price is None:
        # Trả JSON lỗi, kèm status 502 cho dễ debug
        return jsonify({
            "ok": False,
            "error": error,
            "tradeType": trade_type,
            "fiat": fiat
        }), 502

    return jsonify({
        "ok": True,
        "price": price,
        "tradeType": trade_type,
        "fiat": fiat,
        "rows": rows,
        "source": "binance_p2p"
    })


if __name__ == "__main__":
    # Chạy local để test
    app.run(host="0.0.0.0", port=8000, debug=True)
