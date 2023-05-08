from datetime import datetime
from typing import Dict, List

import requests


class ElasticConnection():
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = ""
        self.access_token_expiration_timestamp = 0

    def set_access_token(self):
        if self.access_token:
            current_timestamp = datetime.now().timestamp()
            if current_timestamp < self.access_token_expiration_timestamp:
                return
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials',
        }

        response = requests.get(
            'https://api.moltin.com/oauth/access_token/',
            data=payload,
            timeout=30,
        )
        response.raise_for_status()
        token_card = response.json()

        self.access_token = token_card['access_token']
        self.access_token_expiration_timestamp = token_card['expires']

    def get_products(self):
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }

        response = requests.get(
            'https://api.moltin.com/pcm/products/',
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_product(self, product_id):
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }

        response = requests.get(
            f'https://api.moltin.com/catalog/products/{product_id}/',
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_file_link(self, file_id):
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }

        response = requests.get(
            f'https://api.moltin.com/v2/files/{file_id}/',
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()['data']['link']['href']

    def add_product_to_cart(self, cart_id, product_id, quantity):
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
        }
        payload = {
            "data": {
                "id": product_id,
                "type": "cart_item",
                "quantity": quantity,
            }
        }

        response = requests.post(
            f'https://api.moltin.com/v2/carts/{cart_id}/items/',
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def get_cart(self, cart_id):
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }
        response = requests.get(
            url=f'https://api.moltin.com/v2/carts/{cart_id}/',
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_cart_items(self, cart_id):
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }
        response = requests.get(
            url=f'https://api.moltin.com/v2/carts/{cart_id}/items/',
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def remove_cart_item(self, cart_id, item_id):
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }
        response = requests.delete(
            url=(
                f'https://api.moltin.com/v2/carts/{cart_id}/items/'
                f'{item_id}/'
            ),
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def create_customer(self, name, email):
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }
        payload = {
            'data': {
                'type': 'customer',
                'name': name,
                'email': email,
            }
        }
        response = requests.post(
            url='https://api.moltin.com/v2/customers/',
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def create_product(self, name: str, sku: str, description: str) -> Dict:
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }

        payload = {
            'data': {
                'type': 'product',
                'attributes': {
                    'name': name,
                    'sku': sku,
                    'description': description,
                    'status': 'live',
                    'commodity_type': 'physical',
                },
            },
        }

        response = requests.post(
            url='https://api.moltin.com/pcm/products/',
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def create_products_relationships(
            self,
            hierarchy_id: str,
            node_id: str,
            products_ids: List
    ) -> Dict:
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }

        products = [
            {'type': 'product', 'id': product_id}
            for product_id in products_ids
        ]

        payload = {'data': products}

        response = requests.post(
            url=(
                f'https://api.moltin.com/pcm/hierarchies/{hierarchy_id}/'
                f'nodes/{node_id}/relationships/products/'
            ),
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def create_file(self, file_location: str) -> Dict:
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }

        payload = {
            'file_location': (None, file_location),
        }
        response = requests.post(
            url='https://api.moltin.com/v2/files/',
            headers=headers,
            files=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def create_product_file_relationships(
        self,
        product_id: str,
        files_ids: List
    ) -> None:
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }

        files = [{'type': 'file', 'id': file_id} for file_id in files_ids]
        payload = {'data': files}
        response = requests.post(
            url=(
                f'https://api.moltin.com/pcm/products/{product_id}/'
                'relationships/files/'
            ),
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

    def create_main_image_relationships(
            self,
            product_id: str,
            file_id: str
    ) -> None:
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }

        payload = {'data': {'type': 'file', 'id': file_id}}
        response = requests.post(
            url=(
                f'https://api.moltin.com/pcm/products/{product_id}/'
                'relationships/main_image/'
            ),
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

    def create_flow(
        self,
        enabled: bool,
        description: str,
        slug: str,
        name: str
    ) -> Dict:
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }
        payload = {
            'data': {
                'type': 'flow',
                'name': name,
                'slug': slug,
                'description': description,
                'enabled': enabled,
            }
        }
        response = requests.post(
            url='https://api.moltin.com/v2/flows',
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def create_field(
            self,
            *,
            name: str,
            slug: str,
            field_type: str,
            description: str,
            required: bool,
            enabled: bool,
            flow_id: str
    ) -> Dict:
        self.set_access_token()
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }
        payload = {
            'data': {
                'type': 'field',
                'name': name,
                'slug': slug,
                'field_type': field_type,
                'description': description,
                'required': required,
                'enabled': enabled,
                'relationships': {
                    'flow': {
                        'data': {
                            'type': 'flow',
                            'id': flow_id,
                        },
                    },
                },
            },
        }
        response = requests.post(
            url='https://api.moltin.com/v2/fields',
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()