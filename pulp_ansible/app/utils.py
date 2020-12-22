"""
Custom join for querysets.

Source:
 - https://stackoverflow.com/questions/22902263/django-orm-joining-subquery
 - https://gist.github.com/tusharsrivastava/b5377df199a5b2d0561bbf28609effa8
"""
from django.db.models.fields.related import ForeignObject
from django.db.models.options import Options
from django.db.models.sql.constants import INNER
from django.db.models.sql.datastructures import Join
from django.db.models.sql.where import ExtraWhere


class CustomJoin(Join):
    """
    Custom join for querysets.
    """

    def __init__(
        self, subquery, subquery_params, parent_alias, table_alias, join_type, join_field, nullable
    ):  # noqa
        self.subquery_params = subquery_params
        self.join_type = join_type
        super(CustomJoin, self).__init__(
            subquery, parent_alias, table_alias, join_type, join_field, nullable
        )  # noqa

    def as_sql(self, compiler, connection):
        """
        Generates the full
           INNER JOIN (somequery) alias ON alias.somecol = othertable.othercol, params  # noqa
        clause for this join.
        """
        params = []
        sql = []
        alias_str = "" if self.table_alias == self.table_name else (" %s" % self.table_alias)
        params.extend(self.subquery_params)
        qn1 = compiler.quote_name_unless_alias
        qn2 = connection.ops.quote_name

        sql.append("%s (%s)%s ON (" % (self.join_type, self.table_name, alias_str))
        for index, (lhs_col, rhs_col) in enumerate(self.join_cols):
            if index != 0:
                sql.append(" AND ")
            sql.append(
                "%s.%s = %s.%s"
                % (
                    qn1(self.parent_alias),
                    qn2(lhs_col),
                    qn1(self.table_alias),
                    qn2(rhs_col),
                )
            )
        extra_cond = self.join_field.get_extra_restriction(
            compiler.query.where_class, self.table_alias, self.parent_alias
        )
        if extra_cond:
            extra_sql, extra_params = compiler.compile(extra_cond)
            extra_sql = "AND (%s)" % extra_sql
            params.extend(extra_params)
            sql.append("%s" % extra_sql)
        sql.append(")")
        return " ".join(sql), params


def join_to_queryset(
    table,
    subquery,
    table_field,
    subquery_field,
    queryset,
    alias,
    is_raw=False,  # noqa
    extra_restriction_func=lambda where_class, alias, related_alias: None,
):
    """
    Add a join on `subquery` to `queryset` (having table `table`).
    """
    foreign_object = ForeignObject(
        to=subquery, from_fields=[None], to_fields=[None], rel=None, on_delete=[None]
    )  # noqa
    foreign_object.opts = Options(table._meta)
    foreign_object.opts.model = table
    foreign_object.get_joining_columns = lambda: ((table_field, subquery_field),)
    foreign_object.get_extra_restriction = extra_restriction_func

    subquery_sql, subquery_params = (
        (subquery.query, []) if is_raw else subquery.query.sql_with_params()
    )
    parent_alias = queryset.query.get_initial_alias()  # table._meta.db_table
    join = CustomJoin(
        subquery_sql, subquery_params, parent_alias, alias, INNER, foreign_object, False
    )  # noqa

    queryset.query.join(join)

    # hook for set alias
    join.table_alias = alias
    try:
        # For old < 3.x version of Django
        queryset.query.external_aliases.add(alias)
    except Exception:
        # For newer >= 3.x version of Django
        queryset.query.external_aliases.update({alias: alias})

    return queryset


def join_to_table(
    table,
    table2,
    table_field,
    table2_field,
    queryset,
    alias,
    extra_restriction_func=lambda where_class, alias, related_alias: None,
):
    """
    Add a join on `table2` to `queryset` (having table `table`).
    """
    foreign_object = ForeignObject(
        to=table2, from_fields=[None], to_fields=[None], rel=None, on_delete=[None]
    )  # noqa
    foreign_object.opts = Options(table._meta)
    foreign_object.opts.model = table
    foreign_object.get_joining_columns = lambda: ((table_field, table2_field),)
    foreign_object.get_extra_restriction = extra_restriction_func

    join = Join(table2._meta.db_table, table._meta.db_table, alias, INNER, foreign_object, False)
    queryset.query.join(join)

    # hook for set alias
    join.table_alias = alias
    try:
        # For old < 3.x version of Django
        queryset.query.external_aliases.add(alias)
    except Exception:
        # For newer >= 3.x version of Django
        queryset.query.external_aliases.update({alias: alias})

    return queryset


def get_active_extra_restriction(where_class, alias, related_alias):
    """Gets active extra."""
    where = "{alias}.active = True".format(alias=alias)
    children = [ExtraWhere([where], ())]

    return where_class(children)
