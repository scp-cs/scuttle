extra_link_schema = {
    'type': 'object',
    'properties': {
        'link': {
            'type': 'string'
        },
        'name': {
            'type': ['string', 'null']
        },
        'description': {
            'type': ['string', 'null']
        }
    },
    'required': ['link']
}

link_remove_schema = {
    'type': 'object',
    'properties': {
        'link': {
            'type': 'string'
        }
    },
    'required': ['link']
}