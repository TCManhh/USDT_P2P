from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Dùng endpoint "friendly" như trên web Binance
BINANCE_P2P_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"


def fetch_binance_p2p_price(trade_type="SELL", fiat="VND", rows=3, trans_amount=10000000):
    """
    Gọi Binance P2P, lấy danh sách offer, trả về giá trung bình.
    Mặc định đang lấy:
      - trade_type = "SELL" (người khác bán USDT cho bạn, bạn là buyer)
      - fiat = "VND"
      - rows = 3 offer gần nhất
      - trans_amount = 10,000,000 VND (lọc các quảng cáo vớ vẩn mệnh giá nhỏ)
    """

    trade_type = trade_type.upper()
    fiat = fiat.upper()

    # Header giả làm browser trên trang P2P (tham khảo bài Viblo)
    headers = {
        "Accept": "*/*",
        "Accept-Language": "vi,vi-VN;q=0.9,en;q=0.8",
        "C2CType": "c2c_web",
        "ClientType": "web",
        "Content-Type": "application/json",
        "Lang": "vi",
        "Origin": "https://p2p.binance.com",
        # Thay đổi referer tùy theo BUY/SELL cho đẹp (không bắt buộc nhưng giống web hơn)
        "Referer": f"https://p2p.binance.com/trade/{'buy' if trade_type=='BUY' else 'sell'}/USDT?fiat={fiat}&payment=all-payments",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "X-Passthrough-Token": ""  # để trống như ví dụ trên bài, vẫn dùng được
    }

    # Payload giống trên web, thêm vài field mà Binance đang check
    data = {
        "fiat": fiat,
        "page": 1,
        "rows": rows,
        "tradeType": trade_type,  # "BUY" hoặc "SELL"
        "asset": "USDT",
        "countries": ["VN"],          # tập trung seller VN
        "proMerchantAds": False,
        "shieldMerchantAds": False,
        "filterType": "all",
        "additionalKycVerifyFilter": 0,
        "publisherType": None,
        "payTypes": [],
        "classifies": ["mass", "profession"],
        "transAmount": trans_amount   # tối thiểu 10M VND
    }

    try:
        resp = requests.post(
            BINANCE_P2P_URL,
            headers=headers,
            json=data,
            timeout=10
        )
    except requests.RequestException as e:
        return None, {"error": "network_error", "detail": str(e)}

    if resp.status_code != 200:
        return None, {
            "error": "binance_http_error",
            "status_code": resp.status_code,
            "body": resp.text[:500],
        }

    try:
        payload = resp.json()
    except ValueError:
        return None, {
            "error": "binance_json_error",
            "body": resp.text[:500],
        }

    # Trong các ví dụ public hiện tại, dữ liệu nằm ở payload["data"]
    if not payload or "data" not in payload or not payload["data"]:
        return None, {"error": "no_offers_from_binance", "raw": payload}

    prices = []
    for item in payload["data"]:
        try:
            price_str = item["adv"]["price"]
            price = float(price_str)
            prices.append(price)
        except (KeyError, ValueError, TypeError):
            continue

    if not prices:
        return None, {"error": "no_valid_prices", "raw": payload}

    avg_price = sum(prices) / len(prices)
    return avg_price, None


@app.route("/usdt_p2p_price", methods=["GET"])
def usdt_p2p_price():
    """
    Endpoint: /usdt_p2p_price?tradeType=SELL&fiat=VND&rows=3&amount=10000000

    Trả về JSON:
    {
      "ok": true,
      "price": 25300.0,
      "tradeType": "SELL",
      "fiat": "VND",
      "rows": 3,
      "transAmount": 10000000,
      "source": "binance_p2p"
    }
    """
    trade_type = request.args.get("tradeType", "SELL").upper()
    fiat = request.args.get("fiat", "VND").upper()
    rows_param = request.args.get("rows", "3")
    amount_param = request.args.get("amount", "10000000")

    try:
        rows = int(rows_param)
    except ValueError:
        rows = 3

    try:
        trans_amount = int(amount_param)
    except ValueError:
        trans_amount = 10000000

    rows = max(1, min(rows, 20))

    price, error = fetch_binance_p2p_price(trade_type, fiat, rows, trans_amount)

    if error is not None or price is None:
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
        "transAmount": trans_amount,
        "source": "binance_p2p"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
