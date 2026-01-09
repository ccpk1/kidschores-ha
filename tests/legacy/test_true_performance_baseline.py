"""Enhanced performance instrumentation for KidsChores.

This test measures the actual expensive operations that matter for optimization:
- Full integration setup time
- Entity creation and registration
- Coordinator data loading and processing
- Badge checking operations (PERF: _check_badges_for_kid)
- Overdue chore checking (PERF: _check_overdue_chores)
- Storage persistence operations (PERF: _persist)
- Home Assistant platform operations
- Memory usage analysis
"""

import asyncio
import logging
import re
import time
import tracemalloc
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest

from custom_components.kidschores.const import COORDINATOR, DOMAIN

pytestmark = pytest.mark.slow


class PerfCapture:
    """Capture PERF timing data from coordinator operations."""

    def __init__(self):
        self.operations = {}

    def parse_perf_message(self, message: str) -> None:
        """Extract timing data from PERF log messages."""
        # Pattern: "PERF: operation_name() took 0.123s ..."
        perf_pattern = r"PERF: ([^()]+)\(\) took ([\d.]+)s"
        match = re.search(perf_pattern, message)
        if match:
            operation, duration = match.groups()
            if operation not in self.operations:
                self.operations[operation] = []
            self.operations[operation].append(float(duration))

    def get_summary(self) -> dict[str, dict[str, float]]:
        """Get performance summary statistics."""
        summary = {}
        for op, times in self.operations.items():
            if times:
                summary[op] = {
                    "count": len(times),
                    "total": sum(times),
                    "avg": sum(times) / len(times),
                    "max": max(times),
                    "min": min(times),
                }
        return summary


class PerfLoggingHandler(logging.Handler):
    """Custom logging handler to capture PERF measurements."""

    def __init__(self, perf_capture: PerfCapture):
        super().__init__()
        self.perf_capture = perf_capture

    def emit(self, record):
        if hasattr(record, "getMessage"):
            message = record.getMessage()
            if "PERF:" in message:
                self.perf_capture.parse_perf_message(message)


async def test_true_performance_baseline(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Measure true performance bottlenecks including PERF operations."""

    # Set up PERF data capture
    perf_capture = PerfCapture()
    perf_handler = PerfLoggingHandler(perf_capture)

    # Get the kidschores logger and add our handler
    kc_logger = logging.getLogger("custom_components.kidschores")
    original_level = kc_logger.level
    kc_logger.setLevel(logging.INFO)  # Ensure INFO level to capture PERF messages
    kc_logger.addHandler(perf_handler)

    try:
        # Start memory tracking
        tracemalloc.start()
        baseline_memory = tracemalloc.get_traced_memory()[0]

        # Measure full integration setup
        setup_start = time.perf_counter()

        # Add config entry and setup integration
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        time.perf_counter() - setup_start
        tracemalloc.get_traced_memory()[0] - baseline_memory

        # Get coordinator
        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id][COORDINATOR]

        # Measure entity registry operations
        er_start = time.perf_counter()
        ent_reg = er.async_get(hass)
        entities = er.async_entries_for_config_entry(
            ent_reg, mock_config_entry.entry_id
        )
        time.perf_counter() - er_start

        # Measure device registry operations
        dr_start = time.perf_counter()
        dev_reg = dr.async_get(hass)
        dr.async_entries_for_config_entry(dev_reg, mock_config_entry.entry_id)
        time.perf_counter() - dr_start

        # Measure coordinator operations with PERF capture
        with (
            patch.object(coordinator, "_notify_kid_translated", new=AsyncMock()),
            patch.object(coordinator, "_notify_parents_translated", new=AsyncMock()),
        ):
            # Clear previous PERF data
            perf_capture.operations.clear()

            # Force coordinator refresh to trigger PERF measurements
            refresh_start = time.perf_counter()
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            time.perf_counter() - refresh_start

            # Force overdue checking to trigger PERF measurement
            overdue_start = time.perf_counter()
            await coordinator._check_overdue_chores()
            time.perf_counter() - overdue_start

            # Force badge checking for all kids to trigger PERF measurement
            badge_start = time.perf_counter()
            for kid_id in coordinator.kids_data:
                await coordinator._check_badges_for_kid(kid_id)
            time.perf_counter() - badge_start

            # Force storage persistence to trigger PERF measurement
            persist_start = time.perf_counter()
            coordinator._persist()  # Not async - just call it
            await asyncio.sleep(0.05)  # Give async save time to complete
            time.perf_counter() - persist_start

        # Show PERF operation summary
        perf_summary = perf_capture.get_summary()
        if perf_summary:
            for _op, _stats in perf_summary.items():
                pass
        else:
            pass

        # Measure entity state updates
        states_start = time.perf_counter()
        all_states = hass.states.async_all()
        [
            s
            for s in all_states
            if s.entity_id.startswith("sensor.kc_")
            or s.entity_id.startswith("button.kc_")
            or s.entity_id.startswith("select.kc_")
        ]
        time.perf_counter() - states_start

        # Get final memory usage
        tracemalloc.get_traced_memory()[0] - baseline_memory
        tracemalloc.stop()

        # Dataset scale info

        # Performance ratios
        if len(entities) > 0:
            pass
        if len(coordinator.kids_data) > 0:
            pass

    finally:
        # Restore logging
        kc_logger.removeHandler(perf_handler)
        kc_logger.setLevel(original_level)


async def test_stress_dataset_true_performance(
    hass: HomeAssistant,
    scenario_stress,
) -> None:
    """Measure performance with large stress test dataset (100 kids) including PERF operations."""

    config_entry, _ = scenario_stress

    # Set up PERF data capture
    perf_capture = PerfCapture()
    perf_handler = PerfLoggingHandler(perf_capture)

    # Get the kidschores logger and add our handler
    kc_logger = logging.getLogger("custom_components.kidschores")
    original_level = kc_logger.level
    kc_logger.setLevel(logging.INFO)  # Ensure INFO level to capture PERF messages
    kc_logger.addHandler(perf_handler)

    try:
        # Memory tracking
        tracemalloc.start()
        baseline_memory = tracemalloc.get_traced_memory()[0]

        # Get coordinator (already set up by fixture)
        coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

        # Show dataset scale

        # Clear previous PERF data and test all major operations
        with (
            patch.object(coordinator, "_notify_kid_translated", new=AsyncMock()),
            patch.object(coordinator, "_notify_parents_translated", new=AsyncMock()),
        ):
            perf_capture.operations.clear()

            # Test overdue checking with full dataset
            overdue_start = time.perf_counter()
            await coordinator._check_overdue_chores()
            time.perf_counter() - overdue_start

            # Test badge checking for all kids (this will be the big one!)
            badge_start = time.perf_counter()
            badge_count = 0
            for badge_count, kid_id in enumerate(coordinator.kids_data, 1):
                coordinator._check_badges_for_kid(kid_id)  # Not async - don't await
                if badge_count % 20 == 0:  # Progress indicator
                    pass
            badge_duration = time.perf_counter() - badge_start

            # Test sequential badge processing sample (10 kids)
            concurrent_start = time.perf_counter()
            kid_list = list(coordinator.kids_data.keys())[:10]
            for kid_id in kid_list:
                coordinator._check_badges_for_kid(kid_id)  # Not async
            concurrent_duration = time.perf_counter() - concurrent_start

            # Test full data persistence with large dataset
            persist_start = time.perf_counter()
            coordinator._persist()  # Not async - just call it
            await asyncio.sleep(0.1)  # Give async save time to complete
            time.perf_counter() - persist_start

            # Test coordinator refresh with full dataset
            refresh_start = time.perf_counter()
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            time.perf_counter() - refresh_start

        # Show comprehensive PERF operation breakdown
        perf_summary = perf_capture.get_summary()
        if perf_summary:
            for op, stats in perf_summary.items():
                total_time = stats["total"]
                stats["count"]
                stats["avg"]

                # Calculate per-kid metrics where applicable
                if "check_badges_for_kid" in op and len(coordinator.kids_data) > 0:
                    total_time / len(coordinator.kids_data) * 1000
                elif "check_overdue_chores" in op and len(coordinator.chores_data) > 0:
                    operations = len(coordinator.chores_data) * len(
                        coordinator.kids_data
                    )
                    if operations > 0:
                        total_time / operations * 1000000
        else:
            pass

        # Memory analysis
        tracemalloc.get_traced_memory()[0] - baseline_memory

        # Entity count analysis
        ent_reg = er.async_get(hass)
        entities = er.async_entries_for_config_entry(ent_reg, config_entry.entry_id)

        # Performance ratios
        if len(entities) > 0:
            pass
        if len(coordinator.kids_data) > 0:
            pass

        # Compare sequential vs concurrent badge processing
        sequential_per_kid = badge_duration / len(coordinator.kids_data) * 1000
        concurrent_per_kid = concurrent_duration / 10 * 1000
        speedup = (
            sequential_per_kid / concurrent_per_kid if concurrent_per_kid > 0 else 0
        )
        if speedup > 0:
            pass

        tracemalloc.stop()

    finally:
        # Restore logging
        kc_logger.removeHandler(perf_handler)
        kc_logger.setLevel(original_level)


@pytest.mark.slow  # Mark as slow test
async def test_full_scenario_performance_comprehensive(
    hass: HomeAssistant,
    scenario_full,
) -> None:
    """Comprehensive performance test with full scenario dataset including ALL PERF operations."""

    config_entry, _ = scenario_full

    # Set up PERF data capture
    perf_capture = PerfCapture()
    perf_handler = PerfLoggingHandler(perf_capture)

    # Get the kidschores logger and add our handler
    kc_logger = logging.getLogger("custom_components.kidschores")
    original_level = kc_logger.level
    kc_logger.setLevel(logging.INFO)  # Ensure INFO level to capture PERF messages
    kc_logger.addHandler(perf_handler)

    try:
        # Memory tracking
        tracemalloc.start()
        baseline_memory = tracemalloc.get_traced_memory()[0]

        # Get coordinator (already set up by fixture)
        coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

        # Show dataset scale

        # Clear previous PERF data and test key operations
        with (
            patch.object(coordinator, "_notify_kid_translated", new=AsyncMock()),
            patch.object(coordinator, "_notify_parents_translated", new=AsyncMock()),
        ):
            perf_capture.operations.clear()

            # Test overdue checking with actual data (REPEATED for stable baseline)

            overdue_times = []
            for _ in range(10):
                overdue_start = time.perf_counter()
                await coordinator._check_overdue_chores()
                overdue_duration = (
                    time.perf_counter() - overdue_start
                ) * 1000  # milliseconds
                overdue_times.append(overdue_duration)

            overdue_avg_ms = sum(overdue_times) / len(overdue_times)
            min(overdue_times)
            max(overdue_times)
            len(coordinator.chores_data) * len(coordinator.kids_data)

            # Test badge checking for all kids with real data (CUMULATIVE)
            badge_start = time.perf_counter()
            for kid_id in coordinator.kids_data:
                coordinator._check_badges_for_kid(kid_id)
            badge_duration_ms = (
                time.perf_counter() - badge_start
            ) * 1000  # milliseconds
            badge_duration_ms / len(coordinator.kids_data)
            (badge_duration_ms * 1000) / (
                len(coordinator.kids_data) * len(coordinator.badges_data)
            )

            # Test data persistence (measure queue time precisely)
            persist_start = time.perf_counter()
            coordinator._persist()  # Not async
            persist_queue_us = (
                time.perf_counter() - persist_start
            ) * 1000000  # microseconds

            await asyncio.sleep(0.05)  # Give async save time to complete

            # Performance assertions (generous limits - optimizations should improve these)
            assert overdue_avg_ms < 50, (
                f"Overdue scanning too slow: {overdue_avg_ms:.3f}ms (expected <50ms)"
            )
            assert badge_duration_ms < 1000, (
                f"Badge checking too slow: {badge_duration_ms:.3f}ms (expected <1000ms)"
            )
            assert persist_queue_us < 5000, (
                f"Persistence queueing too slow: {persist_queue_us:.1f}µs (expected <5000µs)"
            )

            # Test coordinator refresh
            refresh_start = time.perf_counter()
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            time.perf_counter() - refresh_start

        # Show comprehensive PERF operation breakdown
        perf_summary = perf_capture.get_summary()
        if perf_summary:
            for op, stats in perf_summary.items():
                total_time = stats["total"]
                stats["count"]
                avg_time = stats["avg"]

                # Show time per call in appropriate units
                if avg_time >= 1 or avg_time >= 0.001:
                    pass
                else:
                    pass

                # Calculate per-kid metrics for badge operations
                if "check_badges_for_kid" in op and len(coordinator.kids_data) > 0:
                    per_kid = total_time / len(coordinator.kids_data)
                    if per_kid >= 0.001:
                        pass
                    else:
                        pass
        else:
            pass

        # Memory analysis
        tracemalloc.get_traced_memory()[0] - baseline_memory

        # Entity registry analysis
        ent_reg = er.async_get(hass)
        entities = er.async_entries_for_config_entry(ent_reg, config_entry.entry_id)

        # Performance ratios
        if len(coordinator.kids_data) > 0:
            pass
        if len(entities) > 0:
            pass
        if len(coordinator.chores_data) > 0:
            chore_ops = len(coordinator.chores_data) * len(coordinator.kids_data)
            if overdue_avg_ms > 0 and chore_ops > 0:
                (overdue_avg_ms * 1000) / chore_ops  # Convert ms to µs, then divide

        tracemalloc.stop()

    finally:
        # Restore logging
        kc_logger.removeHandler(perf_handler)
        kc_logger.setLevel(original_level)


async def test_operation_timing_breakdown(
    hass: HomeAssistant,
    scenario_stress,
) -> None:
    """Break down timing of individual operations to find bottlenecks."""
    config_entry, _ = scenario_stress
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    # Test individual operations timing
    kid_id = list(coordinator.kids_data.keys())[0]  # Get first kid

    with (
        patch.object(coordinator, "_notify_kid_translated", new=AsyncMock()),
        patch.object(coordinator, "_notify_parents_translated", new=AsyncMock()),
    ):
        # Badge processing timing
        start = time.perf_counter()
        coordinator._check_badges_for_kid(kid_id)
        time.perf_counter() - start

        # Overdue check timing
        start = time.perf_counter()
        await coordinator._check_overdue_chores()
        time.perf_counter() - start

        # Data lookup timing
        start = time.perf_counter()
        chore_id = list(coordinator.chores_data.keys())[0]
        for _ in range(1000):
            _ = coordinator.chores_data[chore_id]
        time.perf_counter() - start

        # Entity state update simulation
        start = time.perf_counter()
        coordinator.async_update_listeners()
        await hass.async_block_till_done()
        time.perf_counter() - start
