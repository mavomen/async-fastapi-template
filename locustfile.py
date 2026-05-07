"""Locust load test for FastAPI application."""

from locust import HttpUser, task, between


class FastAPIUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def health_check(self):
        self.client.get("/health")

    @task(2)
    def register_and_login(self):
        # Register
        self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "load@example.com",
                "username": "loaduser",
                "password": "LoadPass1!",
            },
        )
        # Login
        self.client.post(
            "/api/v1/auth/login",
            data={"username": "load@example.com", "password": "LoadPass1!"},
        )

    @task(1)
    def list_users(self):
        self.client.get("/api/v1/users/")
