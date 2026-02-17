app_config_schema = {
    'type': 'object',
    'properties': {
        'SECRET_KEY': {
            'type': 'string'
        },
        'DEBUG': {
            'type': 'bool'
        },
        'DEBUG_DISABLE_WEBHOOKS': {
            'type': 'bool'
        },
    }
}