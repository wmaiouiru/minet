# =============================================================================
# Minet Tiktok API Scraper
# =============================================================================
#
# Tiktok public API "scraper".
#
from ebbe import getpath
from urllib.parse import quote

from minet.utils import sleep_with_entropy
from minet.cookies import coerce_cookie_for_url_from_browser
from minet.web import (
    create_pool_manager,
    create_request_retryer,
    request,
    retrying_method,
)
from minet.tiktok.constants import (
    TIKTOK_DEFAULT_THROTTLE,
    TIKTOK_PUBLIC_API_DEFAULT_TIMEOUT,
    TIKTOK_URL,
    TIKTOK_MIN_TIME_RETRYER,
    TIKTOK_MAX_RANDOM_ADDENDUM,
)
from minet.tiktok.exceptions import (
    TiktokInvalidCookieError,
    TiktokPublicAPIInvalidResponseError,
)
from minet.tiktok.formatters import (
    format_video,
)


def forge_video_search_url(query, offset):
    url = (
        "https://www.tiktok.com/api/search/general/full/?aid=1988&keyword=%s&offset=%s"
        % (quote(query), offset)
    )

    return url


class TiktokAPIScraper(object):
    def __init__(self, cookie="firefox"):
        self.pool_manager = create_pool_manager(
            timeout=TIKTOK_PUBLIC_API_DEFAULT_TIMEOUT
        )

        cookie = coerce_cookie_for_url_from_browser(cookie, TIKTOK_URL)

        if not cookie:
            raise TiktokInvalidCookieError

        self.cookie = cookie
        self.retryer = create_request_retryer(
            min=TIKTOK_MIN_TIME_RETRYER,
        )

    @retrying_method()
    def request_json(self, url):
        headers = {"Cookie": self.cookie}

        response = request(
            url,
            pool_manager=self.pool_manager,
            spoof_ua=True,
            headers=headers,
            known_encoding="utf-8",
        )

        if response.status >= 400:
            raise TiktokPublicAPIInvalidResponseError(
                url, response.status, response.text()
            )

        sleep_with_entropy(TIKTOK_DEFAULT_THROTTLE, TIKTOK_MAX_RANDOM_ADDENDUM)

        return response.json()

    def search_videos(self, query):
        cursor = None

        while True:
            url = forge_video_search_url(query, cursor)

            data = self.request_json(url)

            item_list = data.get("data")

            if not item_list:
                break

            for item in item_list:
                if item["type"] != 1:
                    continue
                item = item["item"]
                yield format_video(item)

            has_next_page = getpath(data, ["has_more"])

            if has_next_page != 1:
                break

            cursor = getpath(data, ["cursor"])
