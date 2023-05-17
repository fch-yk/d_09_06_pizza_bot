import functools
import html
from textwrap import dedent
from typing import Dict

import requests
from environs import Env
from geopy.distance import distance
from redis import Redis
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice,
                      ParseMode, Update)
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          CommandHandler, Filters, MessageHandler,
                          PreCheckoutQueryHandler, Updater)

from elastic_api import ElasticConnection


def fetch_coordinates(apikey, address):
    base_url = "https://geocode-maps.yandex.ru/1.x"
    response = requests.get(base_url,
                            params={
                                "geocode": address,
                                "apikey": apikey,
                                "format": "json",
                            })
    response.raise_for_status()
    found_response = response.json()['response']
    found_places = found_response['GeoObjectCollection']['featureMember']

    if not found_places:
        return None

    most_relevant = found_places[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return float(lat), float(lon)


def get_menu_text():
    return (
        '<b>Наше меню</b>\n\n'
        'Выбирайте, пожалуйста:'
    )


def get_menu_reply_markup(
    elastic_connection: ElasticConnection,
    page_offset: int
) -> InlineKeyboardMarkup:
    page_limit = 8
    products_response = elastic_connection.get_products_page(
        page_limit=page_limit,
        page_offset=page_offset,
    )
    keyboard = []
    if products_response['data']:
        for product in products_response['data']:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        product['attributes']['name'],
                        callback_data=product['id']
                    )
                ]
            )
        total_products_number = products_response['meta']['results']['total']
        pagination_buttons = []
        if page_offset > 0:
            callback_data = f'pagination: {page_offset - page_limit}'
            pagination_buttons.append(
                InlineKeyboardButton(text='<<', callback_data=callback_data)
            )
        if total_products_number > page_offset + page_limit:
            callback_data = f'pagination: {page_offset + page_limit}'
            pagination_buttons.append(
                InlineKeyboardButton(text='>>', callback_data=callback_data)
            )
        if pagination_buttons:
            keyboard.append(pagination_buttons)
    keyboard.append(
        [InlineKeyboardButton(text='Корзина', callback_data='Cart')]
    )
    return InlineKeyboardMarkup(keyboard)


def get_cart_text(cart: Dict, cart_items: Dict) -> str:
    cart_text = '<b>Корзина:</b>\n\n'
    total = cart["data"]["meta"]["display_price"]["with_tax"]["formatted"]

    for cart_item in cart_items['data']:
        quantity = cart_item['quantity']
        display_price = cart_item['meta']['display_price']
        price_with_tax = display_price['with_tax']
        product_text = dedent(
            f'''\
            <em>{html.escape(cart_item['name'], quote=True)}</em>
            {html.escape(cart_item['description'], quote=True)}
            {price_with_tax['unit']['formatted']} за шт.
            <em>{quantity} шт. за {price_with_tax['value']['formatted']}</em>

            '''
        )
        cart_text += product_text

    return f'{cart_text} <b>ИТОГО: {total}</b>'


def get_cart_reply_markup(cart_items: Dict) -> InlineKeyboardMarkup:
    keyboard = []
    if cart_items['data']:
        keyboard.append(
            [InlineKeyboardButton(text='Оформить заказ',
                                  callback_data='Order')]
        )

        for cart_item in cart_items['data']:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        text=f"Убрать {cart_item['name']} из корзины",
                        callback_data=cart_item['id']
                    )
                ]
            )

    keyboard.append(
        [InlineKeyboardButton(text='В меню', callback_data='To menu')]
    )
    return InlineKeyboardMarkup(keyboard)


def remind_about_order(
    context: CallbackContext,
    remind_order_ad: str,
    remind_order_help: str,
) -> None:
    job = context.job
    text = (
        f'<b>Приятного аппетита!</b>\n{html.escape(remind_order_ad)}\n\n'
        f'<em>{html.escape(remind_order_help)}</em>'
    )
    context.bot.send_message(job.context, text=text, parse_mode=ParseMode.HTML)


def start(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection
) -> str:
    reply_markup = get_menu_reply_markup(
        elastic_connection=elastic_connection,
        page_offset=0
    )
    update.message.reply_text(
        get_menu_text(),
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

    return 'HANDLE_MENU'


def handle_menu(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection
) -> str:
    query = update.callback_query
    if not query:
        return 'HANDLE_MENU'
    # CallbackQueries need to be answered,
    # even if no notification to the user is needed
    # Some clients may have trouble otherwise.
    # See https://core.telegram.org/bots/api#callbackquery
    query.answer()
    chat_id = query.from_user.id

    if query.data == 'Cart':
        cart = elastic_connection.get_cart(cart_id=chat_id)
        cart_items = elastic_connection.get_cart_items(cart_id=chat_id)
        cart_text = get_cart_text(cart=cart, cart_items=cart_items)
        reply_markup = get_cart_reply_markup(cart_items=cart_items)
        query.message.edit_text(
            text=cart_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return 'HANDLE_CART'

    if query.data.startswith('pagination: '):
        page_offset = int(query.data.replace('pagination: ', ''))
        reply_markup = get_menu_reply_markup(
            elastic_connection=elastic_connection,
            page_offset=page_offset
        )
        query.message.edit_text(
            text=get_menu_text(),
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return 'HANDLE_MENU'

    product_id = query.data
    product = elastic_connection.get_product(product_id)["data"]
    main_image_id = product['relationships']['main_image']['data']['id']
    image_link = elastic_connection.get_file_link(main_image_id)
    price = product["attributes"]["price"]["RUB"]["amount"]
    formatted_price = '{:.2f}'.format(price)
    caption = (
        f'<b>{html.escape(product["attributes"]["name"], quote=True)}</b>\n\n'
        f'<em>{formatted_price} руб. за шт.</em>\n\n'
        f'{html.escape(product["attributes"]["description"], quote=True)}'
    )

    adding_button = InlineKeyboardButton(
        text='Добавить в корзину',
        callback_data=product_id
    )
    keyboard = [
        [adding_button],
        [InlineKeyboardButton(text='Корзина', callback_data='Cart')],
        [InlineKeyboardButton('Назад', callback_data='Back')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_photo(
        chat_id=chat_id,
        photo=image_link,
        caption=caption,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    context.bot.delete_message(
        chat_id=chat_id,
        message_id=query.message.message_id
    )

    return 'HANDLE_DESCRIPTION'


def handle_description(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection
) -> str:
    query = update.callback_query
    if not query:
        return 'HANDLE_DESCRIPTION'

    chat_id = query.from_user.id
    if query.data == 'Back':
        query.answer()
        reply_markup = get_menu_reply_markup(
            elastic_connection=elastic_connection,
            page_offset=0
        )
        context.bot.send_message(
            chat_id=chat_id,
            text=get_menu_text(),
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        context.bot.delete_message(
            chat_id=chat_id,
            message_id=query.message.message_id
        )
        return 'HANDLE_MENU'

    if query.data == 'Cart':
        query.answer()
        cart = elastic_connection.get_cart(cart_id=chat_id)
        cart_items = elastic_connection.get_cart_items(cart_id=chat_id)
        cart_text = get_cart_text(cart=cart, cart_items=cart_items)
        reply_markup = get_cart_reply_markup(cart_items=cart_items)
        context.bot.send_message(
            chat_id=chat_id,
            text=cart_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        context.bot.delete_message(
            chat_id=chat_id,
            message_id=query.message.message_id
        )
        return 'HANDLE_CART'

    product_id = query.data
    elastic_connection.add_product_to_cart(
        cart_id=chat_id,
        product_id=product_id,
        quantity=1
    )
    query.answer(
        text='Товар был добавлен в корзину'
    )

    return 'HANDLE_DESCRIPTION'


def handle_cart(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection
) -> str:
    query = update.callback_query
    if not query:
        return 'HANDLE_CART'
    query.answer()
    chat_id = query.from_user.id
    if query.data == 'To menu':
        menu_text = get_menu_text()
        reply_markup = get_menu_reply_markup(
            elastic_connection=elastic_connection,
            page_offset=0
        )
        query.message.edit_text(
            text=menu_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

        return 'HANDLE_MENU'

    if query.data == 'Order':
        text = 'Пришлите адрес Вашей электронной почты:'
        reply_markup = InlineKeyboardMarkup([])
        query.message.edit_text(text=text, reply_markup=reply_markup)

        return 'WAITING_EMAIL'

    elastic_connection.remove_cart_item(cart_id=chat_id, item_id=query.data)
    cart = elastic_connection.get_cart(cart_id=chat_id)
    cart_items = elastic_connection.get_cart_items(cart_id=chat_id)

    query.message.edit_text(
        text=get_cart_text(cart=cart, cart_items=cart_items),
        parse_mode=ParseMode.HTML
    )
    query.message.edit_reply_markup(
        reply_markup=get_cart_reply_markup(cart_items=cart_items)
    )

    return 'HANDLE_CART'


def handle_email(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection,
    payment_token: str,
) -> str:
    chat_id = update.message.chat_id
    name = f'Customer_{chat_id}'
    customers_response = elastic_connection.get_customers_by_name(name=name)
    email = update.message.text
    if customers_response['data']:
        customer = customers_response['data'][0]
        if customer['email'] != email:
            elastic_connection.update_customer_email(
                customer_id=customer['id'],
                email=email,
            )
    else:
        elastic_connection.create_customer(name=name, email=email)

    cart_response = elastic_connection.get_cart(cart_id=chat_id)
    price_with_tax = cart_response['data']['meta']['display_price']['with_tax']
    context.bot.send_invoice(
        chat_id=chat_id,
        title='Оплата',
        description='Заказ пиццы',
        payload='pizza-bot-payload',
        provider_token=payment_token,
        currency=price_with_tax['currency'],
        prices=[LabeledPrice('Заказ пиццы', price_with_tax['amount'] * 100)]
    )

    return 'HANDLE_PAYMENT_PRECHECKOUT'


def handle_payment_precheckout(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection
) -> str:
    query = update.pre_checkout_query
    if query.invoice_payload != 'pizza-bot-payload':
        query.answer(ok=False, error_message="Something went wrong...")
    else:
        query.answer(ok=True)
    return 'HANDLE_SUCCESSFUL_PAYMENT'


def handle_successful_payment(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection
) -> str:
    text = (
        '<b>Благодарим Вас за оплату!</b>\n\n'
        'Давайте договоримся о доставке.\n'
        '<em>Пришлите Ваш адрес текстом или геолокацию.</em>'
    )
    update.message.reply_text(text=text, parse_mode=ParseMode.HTML)
    return 'HANDLE_LOCATION'


def get_pizzeria_distance_km(pizzeria):
    return pizzeria['distance_km']


def handle_location(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection,
    ya_api_key: str,
):
    latitude = longitude = None
    if update.message.location:
        latitude = update.message.location.latitude
        longitude = update.message.location.longitude

    if update.message.text:
        coordinates = fetch_coordinates(
            apikey=ya_api_key,
            address=update.message.text
        )
        if coordinates:
            latitude, longitude = coordinates

    if not (latitude and longitude):
        text = (
            'Не удалось определить Ваши координаты.\n'
            'Попробуйте еще раз отправить адрес текстом или геолокацию.'
        )
        update.message.reply_text(text=text)
        return 'HANDLE_LOCATION'

    pizzerias_response = elastic_connection.get_custom_flow_entries(
        slug='pizzerias'
    )
    pizzerias = pizzerias_response['data']
    for pizzeria in pizzerias:
        pizzeria['distance_km'] = distance(
            (latitude, longitude),
            (pizzeria['latitude'], pizzeria['longitude'])
        ).km

    nearest_pizzeria = min(pizzerias, key=get_pizzeria_distance_km)
    delivery_is_possible = True
    if nearest_pizzeria['distance_km'] <= 0.5:
        text = (f'''\
        Может, заберете пиццу из нашей пиццерии неподалеку?
        Она всего в {int(nearest_pizzeria['distance_km']*1000)} метрах от Вас!
        Вот ее адрес: {nearest_pizzeria['address']}

        А можем и бесплатно доставить, нам не сложно.
        ''')
    elif nearest_pizzeria['distance_km'] <= 5:
        text = (f'''\
        Похоже, придется ехать до Вас на самокате.
        Доставка будет стоить 100 рублей. Оплата - курьеру на месте.
        Самовывоз возможен из ближайшей пиццерии.
        Вот ее адрес: {nearest_pizzeria['address']}
        Доставляем или самовывоз?
        ''')
    elif nearest_pizzeria['distance_km'] <= 20:
        text = (f'''\
        Похоже, придется ехать до Вас...
        Доставка будет стоить 300 рублей. Оплата - курьеру на месте.
        Самовывоз возможен из ближайшей пиццерии.
        Вот ее адрес: {nearest_pizzeria['address']}
        Доставляем или самовывоз?
        ''')
    else:
        text = (f'''\
        Простите, но так далеко мы пиццу не доставим.
        Ближайшая пиццерия в {int(nearest_pizzeria['distance_km'])} км. от Вас!
        Самовывоз возможен из ближайшей пиццерии.
        Вот ее адрес: {nearest_pizzeria['address']}
        ''')
        delivery_is_possible = False

    name = f'Customer_{update.message.chat_id}'
    customers_response = elastic_connection.get_customers_by_name(name=name)
    customer = customers_response['data'][0]
    if not (
        customer['latitude'] == latitude and
        customer['longitude'] == longitude
    ):
        elastic_connection.update_customer_location(
            customer_id=customer['id'],
            latitude=latitude,
            longitude=longitude,
        )

    text = dedent(text)
    keyboard = []
    if delivery_is_possible:
        delivery_key = InlineKeyboardButton(
            text='Доставка',
            callback_data=(
                f'{nearest_pizzeria["courier_tg_id"]},'
                f'{latitude},'
                f'{longitude}'
            )
        )
        keyboard.append([delivery_key])

    pickup_key = InlineKeyboardButton(text='Самовывоз', callback_data='Pickup')
    keyboard.append([pickup_key])

    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(text=text, reply_markup=reply_markup)

    return 'HANDLE_DELIVERY_CHOICE'


def handle_delivery_choice(
    update: Update,
    context: CallbackContext,
    elastic_connection: ElasticConnection,
    remind_order_ad: str,
    remind_order_help: str,
    remind_order_wait: str,
) -> str:
    query = update.callback_query
    if not query:
        return 'HANDLE_DELIVERY_CHOICE'
    query.answer()
    chat_id = query.from_user.id
    query.message.edit_reply_markup(reply_markup=None)
    if query.data == 'Pickup':
        text = dedent(
            '''\
            <b>Спасибо!</b>
            Вы выбрали вариант <em>Самовывоз</em>
            Ждем Вас в нашей ближайшей пиццерии!
            '''
        )
        context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
        )
        return 'START'

    courier_tg_id, latitude, longitude = query.data.split(sep=',')
    cart = elastic_connection.get_cart(cart_id=chat_id)
    cart_items = elastic_connection.get_cart_items(cart_id=chat_id)
    cart_text = get_cart_text(cart=cart, cart_items=cart_items)
    cart_text = f'<b>Выполнить доставку:</b>\n\n{cart_text}'
    context.bot.send_message(
        chat_id=int(courier_tg_id),
        text=cart_text,
        parse_mode=ParseMode.HTML
    )
    context.bot.send_location(
        chat_id=int(courier_tg_id),
        latitude=float(latitude),
        longitude=float(longitude),
    )
    reminder_handler = functools.partial(
        remind_about_order,
        remind_order_ad=remind_order_ad,
        remind_order_help=remind_order_help,
    )

    context.job_queue.run_once(
        reminder_handler,
        when=remind_order_wait,
        context=chat_id,
        name=str(chat_id)
    )

    text = dedent(
        '''\
        <b>Спасибо!</b>
        Вы выбрали вариант <em>Доставка</em>
        Мы отправили Ваш заказ курьеру ближайшей пиццерии.
        Доставим заказ в течение 1 часа.
        '''
    )
    context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
    )
    return 'START'


def handle_users_reply(
        update: Update,
        context: CallbackContext,
        redis_connection: Redis,
        elastic_connection: ElasticConnection,
        ya_api_key: str,
        remind_order_ad: str,
        remind_order_help: str,
        remind_order_wait: str,
        payment_token: str,
) -> None:
    if update.message:
        chat_id = update.message.chat_id
    elif update.callback_query:
        chat_id = update.callback_query.from_user.id
    else:
        chat_id = update.effective_user.id

    redis_customer_id = f'pizza_shop_{chat_id}'

    if update.message and update.message.text == '/start':
        user_state = 'START'
    else:
        user_state = redis_connection.get(redis_customer_id)

    if not user_state:
        user_state = 'START'

    location_handler = functools.partial(
        handle_location,
        ya_api_key=ya_api_key,
    )
    delivery_choice_handler = functools.partial(
        handle_delivery_choice,
        remind_order_ad=remind_order_ad,
        remind_order_help=remind_order_help,
        remind_order_wait=remind_order_wait,
    )
    email_handler = functools.partial(
        handle_email,
        payment_token=payment_token,
    )

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'HANDLE_CART': handle_cart,
        'WAITING_EMAIL': email_handler,
        'HANDLE_PAYMENT_PRECHECKOUT': handle_payment_precheckout,
        'HANDLE_SUCCESSFUL_PAYMENT': handle_successful_payment,
        'HANDLE_LOCATION': location_handler,
        'HANDLE_DELIVERY_CHOICE': delivery_choice_handler,
    }
    state_handler = states_functions[user_state]
    next_state = state_handler(update, context, elastic_connection)
    redis_connection.set(redis_customer_id, next_state)


def main():
    env = Env()
    env.read_env()

    with env.prefixed('REDIS_'):
        redis_connection = Redis(
            host=env('HOST'),
            port=env('PORT'),
            password=env('PASSWORD'),
            decode_responses=True
        )

    with env.prefixed('ELASTIC_'):
        elastic_connection = ElasticConnection(
            client_id=env('PATH_CLIENT_ID'),
            client_secret=env('PATH_CLIENT_SECRET'),
        )

    with env.prefixed('REMIND_ORDER_'):
        remind_order_ad = env('AD', 'Заказывайте снова!')
        remind_order_help = env('HELP', 'Если заказ не доставлен - звоните!')
        remind_order_wait = env.int('WAIT', 3600)

    users_reply_handler = functools.partial(
        handle_users_reply,
        redis_connection=redis_connection,
        elastic_connection=elastic_connection,
        ya_api_key=env('YA_API_KEY'),
        remind_order_ad=remind_order_ad,
        remind_order_help=remind_order_help,
        remind_order_wait=remind_order_wait,
        payment_token=env('PAYMENT_TOKEN'),
    )

    updater = Updater(env('PIZZA_BOT_TOKEN'))
    dispatcher = updater.dispatcher
    dispatcher.add_handler(
        MessageHandler(
            filters=(
                Filters.text | Filters.location | Filters.successful_payment
            ),
            callback=users_reply_handler
        )
    )
    dispatcher.add_handler(CommandHandler('start', users_reply_handler))
    dispatcher.add_handler(CallbackQueryHandler(users_reply_handler))
    dispatcher.add_handler(PreCheckoutQueryHandler(users_reply_handler))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
