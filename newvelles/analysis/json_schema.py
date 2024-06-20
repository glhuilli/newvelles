JSON_SCHEMA = {
    '$defs': {
        'concept': {
            'properties': {
                'terms': {
                    'items': {
                        'type': 'string'
                    },
                    'type': 'array'
                },
                'phrases': {
                    'items': {
                        'type': 'string'
                    },
                    'type': 'array'
                },
                'categories': {
                    'items': {
                        'type': 'string'
                    },
                    'type': 'array'
                }
            },
            'required': ['terms', 'phrases', 'categories'],
            'type': 'object'
        }
    },
    'properties': {
        'concepts': {
            'items': {
                '$ref': '#/$defs/concept'
            },
            'type': 'array'
        }
    },
    'type': 'object'
}