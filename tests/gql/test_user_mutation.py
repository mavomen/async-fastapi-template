"""Tests for GraphQL user mutations."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_create_user_mutation(async_client: AsyncClient, db_session: AsyncSession):
    """Test the createUser mutation."""
    mutation = """
      mutation {
        createUser(email: "gqlcreate@example.com", username: "gqlcreate", password: "StrongPass1!", fullName: "GQL Create") {
          id
          email
          username
        }
      }
    """
    response = await async_client.post("/graphql", json={"query": mutation})
    assert response.status_code == 200
    data = response.json()
    assert "errors" not in data
    assert data["data"]["createUser"]["email"] == "gqlcreate@example.com"
