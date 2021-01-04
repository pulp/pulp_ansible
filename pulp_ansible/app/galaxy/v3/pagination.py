from rest_framework import pagination
from rest_framework.response import Response
from rest_framework.utils.urls import remove_query_param, replace_query_param


class LimitOffsetPagination(pagination.LimitOffsetPagination):
    """
    Pagination for V3.

    """

    default_limit = 10
    max_limit = 100

    def get_first_link(self):
        """First link."""
        url = self.request.get_full_path()
        url = replace_query_param(url, self.limit_query_param, self.limit)

        return replace_query_param(url, self.offset_query_param, 0)

    def get_last_link(self):
        """Last link."""
        url = self.request.get_full_path()
        url = replace_query_param(url, self.limit_query_param, self.limit)

        offset = self.count - self.limit if (self.count - self.limit) >= 0 else 0
        return replace_query_param(url, self.offset_query_param, offset)

    def get_next_link(self):
        """Next link."""
        if self.offset + self.limit >= self.count:
            return None

        url = self.request.get_full_path()
        url = replace_query_param(url, self.limit_query_param, self.limit)

        offset = self.offset + self.limit
        return replace_query_param(url, self.offset_query_param, offset)

    def get_previous_link(self):
        """Previous link."""
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

    def get_paginated_response_schema(self, schema):
        """Returns paginated response schema."""
        return {
            "type": "object",
            "properties": {
                "meta": {
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "example": 123,
                        },
                    },
                },
                "links": {
                    "type": "object",
                    "properties": {
                        "first": {
                            "type": "string",
                            "nullable": True,
                        },
                        "previous": {
                            "type": "string",
                            "nullable": True,
                        },
                        "next": {
                            "type": "string",
                            "nullable": True,
                        },
                        "last": {
                            "type": "string",
                            "nullable": True,
                        },
                    },
                },
                "data": schema,
            },
        }

    # Custom methods for working with pulp client
    def init_from_request(self, request):
        """Init form request."""
        self.request = request
        self.offset = self.get_offset(request)
        self.limit = self.get_limit(request)

    def paginate_proxy_response(self, data, count):
        """Paginate proxy response."""
        self.count = count

        if self.count > self.limit and self.template is not None:
            self.display_page_controls = True

        return self.get_paginated_response(data)
