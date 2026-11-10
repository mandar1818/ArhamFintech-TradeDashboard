import asyncio
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

from app.core.exceptions import BSEUpstreamError

# Realistic Indian equity market universe (BSE / Sensex & Nifty 50 constituents)
INDIAN_EQUITIES: List[Tuple[str, float]] = [
    ("RELIANCE", 1315.50),
    ("TCS", 4082.00),
    ("HDFCBANK", 1736.40),
    ("INFY", 1864.25),
    ("ICICIBANK", 1294.80),
    ("SBIN", 826.35),
    ("BHARTIARTL", 1612.90),
    ("ITC", 488.60),
    ("KOTAKBANK", 1776.15),
    ("LT", 3588.00),
    ("HINDUNILVR", 2512.40),
    ("AXISBANK", 1164.75),
    ("BAJFINANCE", 6948.50),
    ("MARUTI", 11845.00),
    ("SUNPHARMA", 1842.30),
    ("TITAN", 3324.10),
    ("ASIANPAINT", 2894.60),
    ("WIPRO", 564.80),
    ("HCLTECH", 1828.45),
    ("TATAMOTORS", 876.20),
    ("NTPC", 404.90),
    ("ONGC", 268.40),
    ("POWERGRID", 323.75),
    ("ULTRACEMCO", 11315.00),
    ("ADANIENT", 2938.50),
    ("JSWSTEEL", 964.30),
    ("TATASTEEL", 152.15),
    ("BAJAJFINSV", 1689.90),
    ("M&M", 2962.00),
    ("DRREDDY", 1274.85),
]

INDIAN_CLIENTS: List[str] = [
    "HDFC Mutual Fund",
    "SBI Mutual Fund",
    "ICICI Prudential AMC",
    "Kotak Institutional Equities",
    "Nippon India MF",
    "Axis Asset Management",
    "Motilal Oswal PMS",
    "Mirae Asset Capital",
    "Zerodha Institutional Desk",
    "Arham Institutional Treasury",
    "DSP Investment Managers",
    "Quant Mutual Fund",
    "Edelweiss Wealth Desk",
    "IIFL Institutional",
    "Bajaj Finserv Treasury",
    "UTI Asset Management",
    "Tata Asset Management",
    "Aditya Birla Sun Life AMC",
    "PPFAS Mutual Fund",
    "Bandhan AMC",
    "Franklin Templeton India",
    "Canara Robeco AMC",
]

ProgressCallback = Callable[[int, str, str], Awaitable[None]]


@dataclass(frozen=True)
class RawTradeRecord:
    trade_id: str
    client: str
    symbol: str
    quantity: int
    price: Decimal
    timestamp: datetime


def _tick_round(value: float) -> Decimal:
    """Round price to standard BSE 0.05 INR tick size."""
    rounded = round(round(value * 20.0) / 20.0, 2)
    return Decimal(f"{max(rounded, 1.00):.2f}")


def _generate_quantity(base_price: float, rng: random.Random) -> int:
    """Generate realistic institutional lot quantity inversely scaled to share price."""
    if base_price >= 6000:
        return rng.randint(10, 350)
    if base_price >= 2000:
        return rng.randint(25, 900)
    if base_price >= 1000:
        return rng.randint(50, 1800)
    return rng.randint(100, 4500)


def _random_bse_market_timestamp(base_utc: datetime, days_back: int, rng: random.Random) -> datetime:
    """Generate a realistic historical UTC timestamp within BSE trading hours (09:15-15:30 IST)."""
    # Keep historical seed records at least 1 day prior to reference time so new pulls sort first.
    day_offset = rng.randint(1, max(days_back, 1))
    trade_date = (base_utc - timedelta(days=day_offset)).date()
    while trade_date.weekday() >= 5:
        trade_date -= timedelta(days=1)

    market_open_minutes = 3 * 60 + 45  # 03:45 UTC
    market_close_minutes = 10 * 60 + 0  # 10:00 UTC
    minute_of_day = rng.randint(market_open_minutes, market_close_minutes)
    second = rng.randint(0, 59)

    return datetime(
        year=trade_date.year,
        month=trade_date.month,
        day=trade_date.day,
        hour=minute_of_day // 60,
        minute=minute_of_day % 60,
        second=second,
        tzinfo=timezone.utc,
    )


class BSEMockService:
    """Simulates the upstream BSE trade feed with realistic Indian market data and latency."""

    def generate_initial_seed_trades(
        self, count: int, reference_time: Optional[datetime] = None, seed: int = 42
    ) -> List[Dict]:
        """Generate `count` deterministic realistic historical Indian stock trades."""
        rng = random.Random(seed)
        now_utc = reference_time or datetime.now(timezone.utc)
        records: List[Dict] = []

        for idx in range(1, count + 1):
            symbol, base_price = rng.choice(INDIAN_EQUITIES)
            client = rng.choice(INDIAN_CLIENTS)
            price = _tick_round(base_price * rng.uniform(0.94, 1.06))
            quantity = _generate_quantity(base_price, rng)
            timestamp = _random_bse_market_timestamp(now_utc, days_back=45, rng=rng)

            records.append(
                {
                    "trade_id": f"BSE-SEED-{idx:06d}",
                    "client": client,
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": price,
                    "timestamp": timestamp,
                    "source": "INITIAL_SEED",
                    "job_id": None,
                    "created_at": now_utc,
                }
            )

        return records

    def generate_live_batch(self, batch_size: int) -> List[RawTradeRecord]:
        """Generate newly executed simulated BSE trades for an ingestion pull."""
        rng = random.Random()
        now_utc = datetime.now(timezone.utc)
        date_tag = now_utc.strftime("%Y%m%d")
        batch_token = uuid.uuid4().hex[:6].upper()
        trades: List[RawTradeRecord] = []

        for idx in range(1, batch_size + 1):
            symbol, base_price = rng.choice(INDIAN_EQUITIES)
            client = rng.choice(INDIAN_CLIENTS)
            price = _tick_round(base_price * rng.uniform(0.97, 1.03))
            quantity = _generate_quantity(base_price, rng)
            timestamp = now_utc - timedelta(seconds=rng.randint(1, 300))

            trades.append(
                RawTradeRecord(
                    trade_id=f"BSE-{date_tag}-{batch_token}-{idx:04d}",
                    client=client,
                    symbol=symbol,
                    quantity=quantity,
                    price=price,
                    timestamp=timestamp,
                )
            )

        return trades

    async def fetch_bse_batch(
        self,
        *,
        delay_seconds: float,
        batch_size: int,
        attempt: int,
        simulate_failure: bool = False,
        simulate_transient_failures: int = 0,
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[RawTradeRecord]:
        """
        Simulate calling the slow upstream BSE exchange batch API without blocking the event loop.
        Emits incremental progress milestones across the configured delay duration.
        """
        should_fail = simulate_failure or (attempt <= simulate_transient_failures)

        if should_fail:
            # Allow a brief handshake pause before simulating upstream exchange failure.
            if delay_seconds > 0:
                await asyncio.sleep(min(delay_seconds * 0.25, 0.75))
            if on_progress is not None:
                await on_progress(
                    35,
                    "BSE Gateway Handshake",
                    "Upstream BSE clearing endpoint timed out or returned HTTP 503.",
                )
            raise BSEUpstreamError(
                "BSE Exchange feed temporarily unavailable (simulated upstream HTTP 503).",
                retryable=True,
            )

        milestones = [
            (20, "Connecting to BSE Gateway", "Authenticated with simulated BSE clearing gateway."),
            (40, "Awaiting BSE Batch Window", "Waiting for exchange trade settlement batch generation."),
            (65, "Downloading Trade Ledger", "Streaming settled equity trade records from BSE feed."),
            (85, "Validating & Deduplicating", "Verifying symbols, prices, and trade identifiers."),
        ]

        if delay_seconds > 0:
            step_sleep = delay_seconds / len(milestones)
            for progress, stage, msg in milestones:
                await asyncio.sleep(step_sleep)
                if on_progress is not None:
                    await on_progress(progress, stage, msg)
        else:
            if on_progress is not None:
                await on_progress(
                    85,
                    "Validating & Deduplicating",
                    "Verifying symbols, prices, and trade identifiers.",
                )

        return self.generate_live_batch(batch_size=batch_size)
