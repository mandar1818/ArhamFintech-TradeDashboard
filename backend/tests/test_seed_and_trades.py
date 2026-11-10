import time

import httpx
from sqlalchemy import func, select

from app.models.trade import Trade
from app.services.seed_service import seed_initial_trades_if_empty


async def test_initial_seed_data_minimum_3000_and_idempotent(app_factory) -> None:
    app, _ = app_factory(seed_trade_count=3100)
    async with app.router.lifespan_context(app):
        with app.state.session_factory() as db:
            total = db.scalar(select(func.count(Trade.id)))
            assert total == 3100

            sample_trade = db.scalar(select(Trade).limit(1))
            assert sample_trade is not None
            assert sample_trade.trade_id.startswith("BSE-SEED-")
            assert sample_trade.quantity > 0
            assert float(sample_trade.price) > 0
            assert sample_trade.client
            assert sample_trade.symbol

        # Re-running seed must be idempotent (no duplicate insertions).
        inserted_again = seed_initial_trades_if_empty(app.state.session_factory, seed_count=3100)
        assert inserted_again == 0
        with app.state.session_factory() as db:
            assert db.scalar(select(func.count(Trade.id))) == 3100


async def test_get_trades_pagination_search_filtering_and_sorting(app_factory) -> None:
    app, _ = app_factory(seed_trade_count=3050)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Default pagination
            resp = await client.get("/getTrades")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 3050
            assert data["page"] == 1
            assert data["page_size"] == 25
            assert len(data["items"]) == 25
            assert data["summary"]["total_trades"] == 3050
            assert data["summary"]["total_quantity"] > 0
            assert data["summary"]["total_value"] > 0
            assert data["summary"]["unique_clients"] >= 10

            # Verify required fields on each trade record
            first_item = data["items"][0]
            for field in ("trade_id", "client", "symbol", "quantity", "price", "timestamp"):
                assert field in first_item

            # 2. Custom pagination
            resp_p2 = await client.get("/getTrades", params={"page": 2, "page_size": 10})
            assert resp_p2.status_code == 200
            p2 = resp_p2.json()
            assert p2["page"] == 2
            assert len(p2["items"]) == 10
            assert p2["items"][0]["trade_id"] != first_item["trade_id"]

            # 3. Symbol filter (case-insensitive)
            resp_sym = await client.get("/getTrades", params={"symbol": "reliance", "page_size": 50})
            assert resp_sym.status_code == 200
            sym_data = resp_sym.json()
            assert sym_data["total"] > 0
            assert all(item["symbol"] == "RELIANCE" for item in sym_data["items"])
            assert sym_data["summary"]["total_trades"] == 3050
            assert sym_data["filtered_summary"]["total_trades"] == sym_data["total"]

            # 4. Client filter
            filters_resp = await client.get("/trades/filters")
            assert filters_resp.status_code == 200
            filters_data = filters_resp.json()
            assert "RELIANCE" in filters_data["symbols"]
            assert len(filters_data["clients"]) >= 10

            chosen_client = filters_data["clients"][0]
            resp_cli = await client.get("/getTrades", params={"client": chosen_client})
            assert resp_cli.status_code == 200
            cli_data = resp_cli.json()
            assert cli_data["total"] > 0
            assert all(item["client"] == chosen_client for item in cli_data["items"])

            # 5. Search by trade_id and safe wildcard escaping
            target_id = first_item["trade_id"]
            resp_search = await client.get("/getTrades", params={"search": target_id})
            assert resp_search.status_code == 200
            assert resp_search.json()["total"] == 1
            assert resp_search.json()["items"][0]["trade_id"] == target_id

            resp_wildcard = await client.get("/getTrades", params={"search": "%_%"})
            assert resp_wildcard.status_code == 200
            assert resp_wildcard.json()["total"] == 0

            # 6. Sorting by price ascending and value descending
            resp_sort_price = await client.get(
                "/getTrades",
                params={"sort_by": "price", "sort_order": "asc", "page_size": 20},
            )
            assert resp_sort_price.status_code == 200
            prices = [item["price"] for item in resp_sort_price.json()["items"]]
            assert prices == sorted(prices)

            resp_sort_val = await client.get(
                "/getTrades",
                params={"sort_by": "value", "sort_order": "desc", "page_size": 20},
            )
            assert resp_sort_val.status_code == 200
            values = [item["trade_value"] for item in resp_sort_val.json()["items"]]
            assert values == sorted(values, reverse=True)

            # 7. Health endpoint
            health_resp = await client.get("/health")
            assert health_resp.status_code == 200
            assert health_resp.json()["total_trades"] == 3050

            # 8. OpenAPI Swagger docs & CORS headers
            docs_resp = await client.get("/docs")
            assert docs_resp.status_code == 200
            openapi_resp = await client.get("/openapi.json")
            assert openapi_resp.status_code == 200
            paths = openapi_resp.json()["paths"]
            assert "/getTrades" in paths
            assert "/pull-trades" in paths
            assert "/events" in paths

            cors_resp = await client.options(
                "/pull-trades",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "POST",
                },
            )
            assert cors_resp.status_code == 200
            assert cors_resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


async def test_get_trades_returns_immediately_during_slow_pull(app_factory) -> None:
    app, _ = app_factory(seed_trade_count=3000, bse_pull_delay_seconds=10.0)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            pull_resp = await client.post("/pull-trades")
            assert pull_resp.status_code == 202

            started = time.perf_counter()
            trades_resp = await client.get("/getTrades")
            elapsed = time.perf_counter() - started

            assert trades_resp.status_code == 200
            assert trades_resp.json()["total"] == 3000
            assert elapsed < 1.0
