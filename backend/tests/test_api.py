"""
Tests for API endpoints.

Tests HTTP status codes, request validation, response structure,
and database persistence through the API layer.
"""

import pytest


class TestCreateAddress:
    def test_create_valid_address(self, client):
        """POST /api/addresses with valid input should return 201."""
        response = client.post(
            "/api/addresses",
            json={"raw_address": "Flat 302, Tower B, Prestige Lakeside, Whitefield, Bangalore 560066"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["raw_address"] == "Flat 302, Tower B, Prestige Lakeside, Whitefield, Bangalore 560066"
        assert data["status"] in ("PARSED", "NEEDS_REVIEW", "UNPARSEABLE", "ERROR")
        assert "id" in data
        assert "warnings" in data

    def test_create_empty_address_rejected(self, client):
        """Empty address should be rejected with 422."""
        response = client.post("/api/addresses", json={"raw_address": ""})
        assert response.status_code == 422

    def test_create_whitespace_address_rejected(self, client):
        """Whitespace-only address should be rejected."""
        response = client.post("/api/addresses", json={"raw_address": "   "})
        assert response.status_code == 422

    def test_create_missing_body(self, client):
        """Missing request body should return 422."""
        response = client.post("/api/addresses")
        assert response.status_code == 422

    def test_create_too_long_address(self, client):
        """Address over 1000 chars should be rejected."""
        response = client.post(
            "/api/addresses",
            json={"raw_address": "A" * 1001},
        )
        assert response.status_code == 422


class TestListAddresses:
    def test_list_empty(self, client):
        """GET /api/addresses with no data should return empty list."""
        response = client.get("/api/addresses")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_after_create(self, client):
        """Should see the created address in the list."""
        client.post("/api/addresses", json={"raw_address": "Flat 302, Bangalore 560066"})
        response = client.get("/api/addresses")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_list_pagination(self, client):
        """Pagination should work correctly."""
        for i in range(5):
            client.post("/api/addresses", json={"raw_address": f"Address {i}, City 560066"})

        response = client.get("/api/addresses?page=1&page_size=2")
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2


class TestGetAddress:
    def test_get_existing(self, client):
        """GET /api/addresses/{id} should return the address."""
        create_resp = client.post("/api/addresses", json={"raw_address": "Flat 302, Bangalore 560066"})
        addr_id = create_resp.json()["id"]

        response = client.get(f"/api/addresses/{addr_id}")
        assert response.status_code == 200
        assert response.json()["id"] == addr_id

    def test_get_nonexistent(self, client):
        """GET /api/addresses/999 should return 404."""
        response = client.get("/api/addresses/999")
        assert response.status_code == 404


class TestUpdateAddress:
    def test_patch_fields(self, client):
        """PATCH should update only provided fields."""
        create_resp = client.post("/api/addresses", json={"raw_address": "Flat 302, Bangalore 560066"})
        addr_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/addresses/{addr_id}",
            json={"city": "Bengaluru", "status": "PARSED"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["city"] == "Bengaluru"
        assert data["status"] == "PARSED"

    def test_patch_invalid_pin(self, client):
        """PATCH with invalid PIN should be rejected."""
        create_resp = client.post("/api/addresses", json={"raw_address": "Flat 302, Bangalore 560066"})
        addr_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/addresses/{addr_id}",
            json={"pin": "123"},
        )
        assert response.status_code == 422

    def test_patch_nonexistent(self, client):
        """PATCH on nonexistent address should return 404."""
        response = client.patch("/api/addresses/999", json={"city": "Delhi"})
        assert response.status_code == 404


class TestReparse:
    def test_reparse_existing(self, client):
        """POST /api/addresses/{id}/parse should re-parse."""
        create_resp = client.post("/api/addresses", json={"raw_address": "Flat 302, Bangalore 560066"})
        addr_id = create_resp.json()["id"]

        response = client.post(f"/api/addresses/{addr_id}/parse")
        assert response.status_code == 200

    def test_reparse_nonexistent(self, client):
        response = client.post("/api/addresses/999/parse")
        assert response.status_code == 404


class TestStats:
    def test_stats_empty(self, client):
        """GET /api/stats with no data should return zeros."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["parsed"] == 0

    def test_stats_after_seed(self, client):
        """Stats should reflect seeded data."""
        client.post("/api/addresses/seed")
        response = client.get("/api/stats")
        data = response.json()
        assert data["total"] == 15


class TestSeed:
    def test_seed_creates_benchmark_data(self, client):
        """POST /api/addresses/seed should create 15 addresses."""
        response = client.post("/api/addresses/seed")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 15

        # Verify they're actually in the database
        list_resp = client.get("/api/addresses")
        assert list_resp.json()["total"] == 15


class TestHealthCheck:
    def test_health(self, client):
        """GET /api/health should return healthy."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestDatabasePersistence:
    def test_address_persists_after_create(self, client):
        """Created address should be retrievable."""
        create_resp = client.post(
            "/api/addresses",
            json={"raw_address": "H.No. 45, Sector 21, Noida, UP 201301"},
        )
        addr_id = create_resp.json()["id"]

        get_resp = client.get(f"/api/addresses/{addr_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["raw_address"] == "H.No. 45, Sector 21, Noida, UP 201301"

    def test_update_persists(self, client):
        """Updated fields should persist across requests."""
        create_resp = client.post("/api/addresses", json={"raw_address": "Test address, Delhi"})
        addr_id = create_resp.json()["id"]

        client.patch(f"/api/addresses/{addr_id}", json={"city": "New Delhi", "pin": "110001"})

        get_resp = client.get(f"/api/addresses/{addr_id}")
        data = get_resp.json()
        assert data["city"] == "New Delhi"
        assert data["pin"] == "110001"
