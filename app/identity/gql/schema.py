"""Strawberry GraphQL schema definition."""

import strawberry

from app.identity.gql.mutations.user_mutation import UserMutation
from app.identity.gql.queries.user_query import UserQuery
from app.identity.gql.subscriptions.user_subscription import UserSubscription


@strawberry.type
class Query(UserQuery):
    """
    Root Query - all read operations are inherited from UserQuery.
    """


@strawberry.type
class Mutation(UserMutation):
    """
    Root Mutation - all create/update/delete operations are inherited from UserMutation.
    """


@strawberry.type
class Subscription(UserSubscription):
    """
    Root Subscription - real-time event streams.
    """


schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
