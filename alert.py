
import requests
url = "https://api.kite.trade/alerts"
API_KEY='6ra48xexz4hvmalc'
access_token='4g1ywEsE10YeQplWgFYlbiB3f1avLyrG'
headers = {
    "X-Kite-Version": "3",
    "Authorization": f"token {API_KEY}:{access_token}"
}

payload = {
    "name": "DNAMEDIA",
    "lhs_exchange": "NSE",
    "lhs_tradingsymbol": "DNAMEDIA",
    "lhs_attribute": "LastTradedPrice",
    "operator": ">=",
    "rhs_type": "constant",
    "type": "simple",
    "rhs_constant": "27000"
}

response = requests.post(url, headers=headers, data=payload)
print(response.json())
