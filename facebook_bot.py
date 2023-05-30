import functools

import requests
from environs import Env
from flask import Flask, request
from redis import Redis

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
    ELASTIC_OTHERS_NODE_ID = env('OTHERS_NODE_ID')
with env.prefixed('REDIS_'):
    redis_connection = Redis(
        host=env('HOST'),
        port=env('PORT'),
        password=env('PASSWORD'),
        decode_responses=True
    )

LOGO_URL = env('LOGO_URL')
ADDITIONAL_LOGO_URL = env('ADDITIONAL_LOGO_URL')


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
        "https://graph.facebook.com/v17.0/me/messages",
        params=params,
        headers=headers,
        json=request_content,
        timeout=30
    )
    response.raise_for_status()


def send_menu(recipient_id, menu_subtitle, node_id):
    products_response = elastic_connection.get_node_products(
        catalog_id=ELASTIC_CATALOG_ID,
        node_id=node_id,
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
            'subtitle': menu_subtitle,
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

    buttons = []
    if node_id == ELASTIC_MAIN_NODE_ID:
        nodes_response = elastic_connection.get_node_children(
            catalog_id=ELASTIC_CATALOG_ID,
            node_id=ELASTIC_OTHERS_NODE_ID,
        )
        for node in nodes_response['data']:
            buttons.append(
                {
                    'type': 'postback',
                    'title': node['attributes']['name'],
                    'payload': node['id'],
                }
            )

        menu_items.append(
            {
                'title': 'Не нашли нужную пиццу?',
                'image_url': ADDITIONAL_LOGO_URL,
                'subtitle': (
                    'Остальные пиццы можно посмотреть в одной из категорий'
                ),
                'buttons': buttons,
            }
        )
    else:
        buttons.append(
            {
                'type': 'postback',
                'title': 'Основные',
                'payload': ELASTIC_MAIN_NODE_ID,
            }
        )
        menu_items.append(
            {
                'title': 'Не нашли нужную пиццу?',
                'image_url': ADDITIONAL_LOGO_URL,
                'subtitle': (
                    'Вернитесь в меню Основные'
                ),
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
        "https://graph.facebook.com/v17.0/me/messages",
        params=params,
        headers=headers,
        json=request_content,
        timeout=30
    )
    response.raise_for_status()
    return 'HANDLE_MENU'


def handle_menu(recipient_id, postback_title, postback_payload):
    if not postback_payload:
        send_message(
            recipient_id=recipient_id,
            message_text=(
                'Нажмите кнопку для выбора пиццы, перехода к корзине '
                'или перехода в другое меню. '
                'Отправьте /start для перехода в основное меню.'
            )
        )
        return 'HANDLE_MENU'
    send_menu(
        recipient_id=recipient_id,
        menu_subtitle=postback_title,
        node_id=postback_payload,
    )
    return 'HANDLE_MENU'


def handle_start(recipient_id):
    send_menu(
        recipient_id=recipient_id,
        menu_subtitle='Основные',
        node_id=ELASTIC_MAIN_NODE_ID,
    )
    return 'HANDLE_MENU'


def handle_users_reply(
    sender_id,
    *,
    message_text='',
    postback_title='',
    postback_payload='',
):
    menu_handler = functools.partial(
        handle_menu,
        postback_title=postback_title,
        postback_payload=postback_payload,
    )
    states_functions = {
        'START': handle_start,
        'HANDLE_MENU': menu_handler,
    }
    redis_customer_id = f'fb_pizza_shop_{sender_id}'
    if message_text == '/start':
        user_state = 'START'
    else:
        user_state = redis_connection.get(redis_customer_id)

    if not user_state or user_state not in states_functions.keys():
        user_state = 'START'

    state_handler = states_functions[user_state]
    next_state = state_handler(recipient_id=sender_id)
    redis_connection.set(redis_customer_id, next_state)


@app.route('/', methods=['GET'])
def verify():
    """
    When Facebook verifies webhook callback url, it will send GET HTTP request,
    that triggers this method. This method checks FACEBOOK_VERIFY_TOKEN.
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
    Facebook sends POST HTTP request to our webhook, that triggers this method.
    """
    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):
                    handle_users_reply(
                        sender_id=messaging_event["sender"]["id"],
                        message_text=messaging_event["message"]["text"],
                    )
                if messaging_event.get("postback"):
                    postback = messaging_event["postback"]
                    handle_users_reply(
                        sender_id=messaging_event["sender"]["id"],
                        postback_title=postback["title"],
                        postback_payload=postback["payload"],
                    )

    return "ok", 200


if __name__ == '__main__':
    app.run(debug=True)
