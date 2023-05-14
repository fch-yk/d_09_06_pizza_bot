from environs import Env

from elastic_api import ElasticConnection


def main():
    env = Env()
    env.read_env()
    with env.prefixed('ELASTIC_'):
        elastic_connection = ElasticConnection(
            client_id=env('PATH_CLIENT_ID'),
            client_secret=env('PATH_CLIENT_SECRET'),
        )

    flow_creation_response = elastic_connection.create_flow(
        enabled=True,
        description='Extends the default customer object',
        slug='customers',
        name='Customers',
    )

    flow_id = flow_creation_response['data']['id']

    elastic_connection.create_field(
        name='Longitude',
        slug='longitude',
        field_type='float',
        description='Longitude',
        required=False,
        enabled=True,
        flow_id=flow_id
    )
    elastic_connection.create_field(
        name='Latitude',
        slug='latitude',
        field_type='float',
        description='Latitude',
        required=False,
        enabled=True,
        flow_id=flow_id
    )


if __name__ == '__main__':
    main()
