from minet.utils import resolve, create_safe_pool

URLS = [
    'http://bit.ly/2KkpxiW',

    # Self loop
    'https://demo.cyotek.com/features/redirectlooptest.php',
    'https://bit.ly/2gnvlgb',

    # Meta refresh & UA nonsense
    'http://bit.ly/2YupNmj',

    # Invalid URL
    'http://www.outremersbeyou.com/talent-de-la-semaine-la-designer-comorienne-aisha-wadaane-je-suis-fiere-de-mes-origines/',

    # Refresh header
    'http://la-grange.net/2015/03/26/refresh/',

    # GET & UA nonsense
    'https://ebay.us/BUkuxU'
]

http = create_safe_pool()

for url in URLS:
    print()
    error, stack = resolve(http, url, follow_meta_refresh=True)
    print(error)
    for item in stack:
        print(item)
