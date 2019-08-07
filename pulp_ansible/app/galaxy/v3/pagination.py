from rest_framework import pagination
from rest_framework.response import Response
from rest_framework.utils.urls import remove_query_param, replace_query_param


class LimitOffsetPagination(pagination.LimitOffsetPagination):
    """
    Custom limit offset pagination for Galaxy API v3.

    Returns results in the following format::

        "meta": {
            "count": 24
        },
        "links": {
            "first": "http://example.com/articles?offset=0&limit=8",
            "prev": "http://example.com/articles?offset=16&limit=8",
            "next": "http://example.com/articles?offset=24&limit=8",
            "last": "http://example.com/articles?offset=48&limit=8"
        },
        "data": [
            ...
        ]
    """

    default_limit = 10
    max_limit = 100

    def get_first_link(self):
        """Returns link to the first page."""
        url = self.request.get_full_path()
        url = replace_query_param(url, self.limit_query_param, self.limit)

        return replace_query_param(url, self.offset_query_param, 0)

    def get_last_link(self):
        """Returns link to the last page."""
        url = self.request.get_full_path()
        url = replace_query_param(url, self.limit_query_param, self.limit)

        offset = self.count - self.limit if (self.count - self.limit) >= 0 else 0
        return replace_query_param(url, self.offset_query_param, offset)

    def get_next_link(self):
        """Returns link to the next page."""
        if self.offset + self.limit >= self.count:
            return None

        url = self.request.get_full_path()
        url = replace_query_param(url, self.limit_query_param, self.limit)

        offset = self.offset + self.limit
        return replace_query_param(url, self.offset_query_param, offset)

    def get_previous_link(self):
        """Returns link to the previous page."""
        if self.offset <= 0:
            return None

        url = self.request.get_full_path()
        url = replace_query_param(url, self.limit_query_param, self.limit)

        if self.offset - self.limit <= 0:
            return remove_query_param(url, self.offset_query_param)

        offset = self.offset - self.limit
        return replace_query_param(url, self.offset_query_param, offset)

    def get_paginated_response(self, data):
        """Returns paginated response."""
        return Response(
            {
                "meta": {"count": self.count},
                "links": {
                    "first": self.get_first_link(),
                    "previous": self.get_previous_link(),
                    "next": self.get_next_link(),
                    "last": self.get_last_link(),
                },
                "data": data,
            }
        )
