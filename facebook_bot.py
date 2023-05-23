import requests
from environs import Env
from flask import Flask, request

from elastic_api import ElasticConnection

app = Flask(__name__)
env = Env()
env.read_env()
with env.prefixed('FACEBOOK_'):
    FACEBOOK_PAGE_ACCESS_TOKEN = env("PAGE_ACCESS_TOKEN")
    FACEBOOK_VERIFY_TOKEN = env("VERIFY_TOKEN")
with env.prefixed('ELASTIC_'):
    elastic_connection = ElasticConnection(
        client_id=env('PATH_CLIENT_ID'),
        client_secret=env('PATH_CLIENT_SECRET'),
    )
    ELASTIC_CATALOG_ID = env('CATALOG_ID')
    ELASTIC_MAIN_NODE_ID = env('MAIN_NODE_ID')

LOGO_URL = env('LOGO_URL')


@app.route('/', methods=['GET'])
def verify():
    """
    При верификации вебхука у Facebook он отправит запрос на этот адрес.
    На него нужно ответить VERIFY_TOKEN.
    """
    if request.args.get("hub.mode") == "subscribe" and\
            request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == FACEBOOK_VERIFY_TOKEN:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200


@app.route('/', methods=['POST'])
def webhook():
    """
    Основной вебхук, на который будут приходить сообщения от Facebook.
    """
    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    print(messaging_event)
                    sender_id = messaging_event["sender"]["id"]
                    send_menu(sender_id)
    return "ok", 200


def send_message(recipient_id, message_text):
    params = {"access_token": FACEBOOK_PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    request_content = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    }
    response = requests.post(
        "https://graph.facebook.com/v16.0/me/messages",
        params=params,
        headers=headers,
        json=request_content,
        timeout=30
    )
    response.raise_for_status()


def send_menu(recipient_id):
    products_response = elastic_connection.get_node_products(
        catalog_id=ELASTIC_CATALOG_ID,
        node_id=ELASTIC_MAIN_NODE_ID,
    )
    menu_items = []
    buttons = [
        {
            'type': 'postback',
            'title': 'Корзина',
            'payload': 'cart',
        },
        {
            'type': 'postback',
            'title': 'Сделать заказ',
            'payload': 'order',
        },
    ]
    menu_items.append(
        {
            'title': 'Меню',
            'image_url': LOGO_URL,
            'subtitle': 'Выбирайте пиццу!',
            'buttons': buttons,
        }
    )
    for product in products_response['data']:
        product_id = product['id']
        buttons = []
        buttons.append(
            {
                'type': 'postback',
                'title': 'Добавить в корзину',
                'payload': product_id,
            }
        )
        product_name = product['attributes']['name']
        main_image_id = product['relationships']['main_image']['data']['id']
        image_url = elastic_connection.get_file_link(main_image_id)
        price = product["attributes"]["price"]["RUB"]["amount"]
        formatted_price = '{:.2f}'.format(price)
        menu_items.append(
            {
                'title': f'{product_name} ({formatted_price} руб.)',
                'image_url': image_url,
                'subtitle': product['attributes']['description'],
                'buttons': buttons,
            }
        )
    request_content = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": menu_items
                }
            }
        }
    }
    params = {"access_token": FACEBOOK_PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    response = requests.post(
        "https://graph.facebook.com/v16.0/me/messages",
        params=params,
        headers=headers,
        json=request_content,
        timeout=30
    )
    response.raise_for_status()


if __name__ == '__main__':
    app.run(debug=True)
