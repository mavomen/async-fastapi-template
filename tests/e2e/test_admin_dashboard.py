"""Playwright E2E tests for the admin dashboard.

These tests require:
  1. A running dev server (auto-started by the e2e_base_url fixture)
  2. Chromium installed via ``playwright install chromium``
  3. A seeded superuser (id=1)

Run with:  poetry run pytest -m e2e --no-cov
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.e2e]


class TestDashboardLoad:
    def test_dashboard_renders(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/admin")
        heading = page.locator("h1")
        heading.wait_for(state="visible", timeout=10000)
        assert "Dashboard" in heading.inner_text()

    def test_dashboard_shows_model_cards(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/admin")
        page.wait_for_load_state("networkidle")
        links = page.locator("a:has-text('Manage')")
        assert links.count() >= 5, f"Expected at least 5 model cards, got {links.count()}"

    def test_dashboard_nav_links(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/admin")
        nav = page.locator("nav")
        assert nav.count() > 0
        api_docs = page.locator("a:has-text('API Docs')")
        assert api_docs.count() > 0


class TestUserListFlow:
    def test_user_list_loads(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/admin/users")
        heading = page.locator("h1")
        heading.wait_for(state="visible", timeout=10000)
        assert "User" in heading.inner_text()

    def test_user_list_has_table(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/admin/users")
        page.wait_for_load_state("networkidle")
        table = page.locator("#table-wrapper table")
        table.wait_for(state="visible", timeout=10000)
        assert table.count() > 0

    def test_user_list_has_search(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/admin/users")
        search = page.locator("input[name='search']")
        search.wait_for(state="visible", timeout=10000)
        assert search.count() > 0

    def test_user_list_has_create_button(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/admin/users")
        create_link = page.locator("a:has-text('Create')")
        create_link.wait_for(state="visible", timeout=10000)
        assert create_link.count() > 0


class TestUserDetailFlow:
    def test_user_detail_loads(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/admin/users/1")
        page.wait_for_load_state("networkidle")
        heading = page.locator("h1")
        heading.wait_for(state="visible", timeout=10000)
        assert "Detail" in heading.inner_text() or "User" in heading.inner_text()


class TestUserSearchFlow:
    def test_search_triggers_htmx(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/admin/users")
        page.wait_for_load_state("networkidle")
        search_input = page.locator("input[name='search']")
        search_input.fill("admin")
        search_input.press("Enter")
        page.wait_for_timeout(1000)


class TestUserPagination:
    def test_pagination_controls_present(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/admin/users")
        page.wait_for_load_state("networkidle")
        prev_link = page.locator("a:has-text('Previous')")
        next_link = page.locator("a:has-text('Next')")
        assert prev_link.count() + next_link.count() > 0


class TestRoleListFlow:
    def test_role_list_loads(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/admin/roles")
        page.wait_for_load_state("networkidle")
        heading = page.locator("h1")
        heading.wait_for(state="visible", timeout=10000)
        assert "Role" in heading.inner_text()


class TestTrashedListFlow:
    def test_trashed_users_page(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/admin/users/trashed")
        page.wait_for_load_state("networkidle")
        heading = page.locator("h1")
        heading.wait_for(state="visible", timeout=10000)


class TestSessionManagement:
    def test_sessions_page_loads(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/admin/sessions")
        page.wait_for_load_state("networkidle")
        heading = page.locator("h1")
        heading.wait_for(state="visible", timeout=10000)
        assert "Session" in heading.inner_text()


class TestProfilePage:
    def test_profile_page_loads(self, e2e_page: object) -> None:
        page = e2e_page
        page.goto("/profile")
        page.wait_for_load_state("networkidle")
        heading = page.locator("h1")
        heading.wait_for(state="visible", timeout=10000)
        assert "Profile" in heading.inner_text()
