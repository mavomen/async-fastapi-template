"""Locust load test for FastAPI application."""

import uuid
from locust import HttpUser, task, between


class FastAPIUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def health_check(self):
        self.client.get("/health")

    @task(2)
    def register_and_login(self):
        unique_id = uuid.uuid4().hex[:8]
        self.client.post(
            "/api/v1/auth/register",
            json={
                "email": f"load-{unique_id}@example.com",
                "username": f"loaduser-{unique_id}",
                "password": "LoadPass1!",
            },
        )
        self.client.post(
            "/api/v1/auth/login",
            data={"username": f"load-{unique_id}@example.com", "password": "LoadPass1!"},
        )

    @task(1)
    def list_users(self):
        self.client.get("/api/v1/users/")
