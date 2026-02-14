"""Reporting helper functions for KidsChores services.

This module provides read-only data shaping for report and export services.
Service handlers should delegate heavy composition logic here and remain thin.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from .. import const
from ..utils.dt_utils import dt_parse

if TYPE_CHECKING:
    from ..type_defs import (
        ActivityReportResponse,
        NormalizedExportResponse,
        ReportDailyBlock,
        ReportRangeResult,
    )


def resolve_report_range(
    mode: str,
    start_date: str | datetime | None,
    end_date: str | datetime | None,
    timezone_name: str = "UTC",
    now_utc: datetime | None = None,
) -> ReportRangeResult:
    """Resolve report range into timezone-aware ISO boundaries.

    Args:
        mode: Range mode (`last_7_days`, `last_30_days`, `custom`)
        start_date: Optional custom start date
        end_date: Optional custom end date
        timezone_name: Timezone label for response metadata
        now_utc: Optional override for deterministic tests

    Returns:
        Resolved range metadata including mode and ISO boundaries
    """
    now = now_utc or datetime.now(UTC)

    start_dt: datetime | None
    end_dt: datetime | None

    if mode == const.REPORT_RANGE_MODE_LAST_7_DAYS:
        start_dt = now - timedelta(days=7)
        end_dt = now
    elif mode == const.REPORT_RANGE_MODE_LAST_30_DAYS:
        start_dt = now - timedelta(days=30)
        end_dt = now
    else:
        start_dt = _coerce_datetime(start_date)
        end_dt = _coerce_datetime(end_date)
        if start_dt is None or end_dt is None:
            raise ValueError("Custom report range requires start_date and end_date")

    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=UTC)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=UTC)

    return {
        "mode": mode,
        "start_iso": start_dt.isoformat(),
        "end_iso": end_dt.isoformat(),
        "timezone": timezone_name,
    }


def build_activity_report(
    kids_data: dict[str, Any],
    range_result: ReportRangeResult,
    kid_id: str | None = None,
    report_title: str | None = None,
) -> ActivityReportResponse:
    """Build a markdown activity report from ledger data.

    This is a read-only projection and does not mutate coordinator storage.
    """
    start_dt = _coerce_datetime(range_result["start_iso"])
    end_dt = _coerce_datetime(range_result["end_iso"])
    if start_dt is None or end_dt is None:
        raise ValueError("Invalid report range")

    kid_ids = [kid_id] if kid_id else list(kids_data.keys())
    daily_aggregate: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"earned": 0.0, "spent": 0.0, "transactions": 0}
    )

    total_earned = 0.0
    total_spent = 0.0
    transactions_count = 0

    for candidate_kid_id in kid_ids:
        kid_info = kids_data.get(candidate_kid_id, {})
        for entry in _iter_ledger_entries_in_range(kid_info, start_dt, end_dt):
            amount = float(entry.get(const.DATA_LEDGER_AMOUNT, 0.0))
            timestamp = str(entry.get(const.DATA_LEDGER_TIMESTAMP, ""))
            day = timestamp[: const.ISO_DATE_STRING_LENGTH]

            if amount >= 0:
                total_earned += amount
                daily_aggregate[day]["earned"] = (
                    float(daily_aggregate[day]["earned"]) + amount
                )
            else:
                spent = abs(amount)
                total_spent += spent
                daily_aggregate[day]["spent"] = (
                    float(daily_aggregate[day]["spent"]) + spent
                )

            daily_aggregate[day]["transactions"] = (
                int(daily_aggregate[day]["transactions"]) + 1
            )
            transactions_count += 1

    daily_blocks: list[ReportDailyBlock] = []
    for day in sorted(daily_aggregate.keys(), reverse=True):
        earned = round(
            float(daily_aggregate[day]["earned"]), const.DATA_FLOAT_PRECISION
        )
        spent = round(float(daily_aggregate[day]["spent"]), const.DATA_FLOAT_PRECISION)
        net = round(earned - spent, const.DATA_FLOAT_PRECISION)
        tx_count = int(daily_aggregate[day]["transactions"])

        daily_blocks.append(
            {
                "date": day,
                "earned": earned,
                "spent": spent,
                "net": net,
                "transactions": tx_count,
                "markdown_section": (
                    f"### {day}\n"
                    f"- Earned: {earned}\n"
                    f"- Spent: {spent}\n"
                    f"- Net: {net}\n"
                    f"- Transactions: {tx_count}"
                ),
            }
        )

    markdown = _render_report_markdown(
        report_title=report_title,
        range_result=range_result,
        daily_blocks=daily_blocks,
    )

    supplemental = _build_supplemental_period_rollup(kids_data, kid_ids)

    return {
        "range": range_result,
        "scope": {
            "kid_filter_applied": kid_id is not None,
            "kid_ids": kid_ids,
        },
        "summary": {
            "total_earned": round(total_earned, const.DATA_FLOAT_PRECISION),
            "total_spent": round(total_spent, const.DATA_FLOAT_PRECISION),
            "net": round(total_earned - total_spent, const.DATA_FLOAT_PRECISION),
            "transactions_count": transactions_count,
        },
        "daily": daily_blocks,
        "markdown": markdown,
        "supplemental": supplemental,
        "delivery": {
            "notify_attempted": False,
            "notify_service": None,
            "delivered": False,
        },
    }


def build_normalized_export(
    kids_data: dict[str, Any],
    chores_data: dict[str, Any],
    rewards_data: dict[str, Any],
    parents_data: dict[str, Any],
    bonuses_data: dict[str, Any],
    penalties_data: dict[str, Any],
    range_result: ReportRangeResult,
    kid_id: str | None = None,
    include_ledger: bool = True,
    include_period_summaries: bool = True,
    include_items: bool = True,
    include_id_map: bool = True,
) -> NormalizedExportResponse:
    """Build normalized export payload with UUID-to-name mapping."""
    start_dt = _coerce_datetime(range_result["start_iso"])
    end_dt = _coerce_datetime(range_result["end_iso"])
    if start_dt is None or end_dt is None:
        raise ValueError("Invalid export range")

    id_map = _build_id_map(
        kids_data,
        chores_data,
        rewards_data,
        parents_data,
        bonuses_data,
        penalties_data,
    )

    selected_kid_ids = [kid_id] if kid_id else list(kids_data.keys())

    ledger_entries: list[dict[str, Any]] = []
    if include_ledger:
        for candidate_kid_id in selected_kid_ids:
            kid_info = kids_data.get(candidate_kid_id, {})
            kid_name = str(kid_info.get(const.DATA_KID_NAME, candidate_kid_id))
            for entry in _iter_ledger_entries_in_range(kid_info, start_dt, end_dt):
                reference_id = entry.get(const.DATA_LEDGER_REFERENCE_ID)
                ledger_entries.append(
                    {
                        "kid_id": candidate_kid_id,
                        "kid_name": kid_name,
                        "timestamp": entry.get(const.DATA_LEDGER_TIMESTAMP),
                        "amount": entry.get(const.DATA_LEDGER_AMOUNT),
                        "balance_after": entry.get(const.DATA_LEDGER_BALANCE_AFTER),
                        "source": entry.get(const.DATA_LEDGER_SOURCE),
                        "reference_id": reference_id,
                        "reference_name": _resolve_reference_name(id_map, reference_id),
                        "item_name": entry.get(const.DATA_LEDGER_ITEM_NAME),
                    }
                )

    period_summaries: dict[str, Any] = {}
    if include_period_summaries:
        for candidate_kid_id in selected_kid_ids:
            kid_info = kids_data.get(candidate_kid_id, {})
            period_summaries[candidate_kid_id] = {
                const.DATA_KID_POINT_PERIODS: kid_info.get(
                    const.DATA_KID_POINT_PERIODS, {}
                ),
                const.DATA_KID_CHORE_PERIODS: kid_info.get(
                    const.DATA_KID_CHORE_PERIODS, {}
                ),
                const.DATA_KID_REWARD_PERIODS: kid_info.get(
                    const.DATA_KID_REWARD_PERIODS, {}
                ),
            }

    normalized_kids = []
    if include_items:
        for candidate_kid_id in selected_kid_ids:
            kid_info = kids_data.get(candidate_kid_id, {})
            normalized_kids.append(
                {
                    "kid_id": candidate_kid_id,
                    "name": kid_info.get(const.DATA_KID_NAME),
                    "points": kid_info.get(const.DATA_KID_POINTS),
                }
            )

    return {
        "meta": {
            "export_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "range": range_result,
            "filters": {
                "kid_id": kid_id,
                "include_ledger": include_ledger,
                "include_period_summaries": include_period_summaries,
                "include_items": include_items,
                "include_id_map": include_id_map,
            },
        },
        "id_map": id_map if include_id_map else {},
        "kids": normalized_kids,
        "ledger_entries": ledger_entries,
        "period_summaries": period_summaries,
        "raw_refs": {
            "kid_ids": selected_kid_ids,
        },
    }


def _build_id_map(
    kids_data: dict[str, Any],
    chores_data: dict[str, Any],
    rewards_data: dict[str, Any],
    parents_data: dict[str, Any],
    bonuses_data: dict[str, Any],
    penalties_data: dict[str, Any],
) -> dict[str, dict[str, str]]:
    """Build UUID-to-name map for normalized export."""
    return {
        const.DATA_KIDS: {
            str(kid_uuid): str(data.get(const.DATA_KID_NAME, kid_uuid))
            for kid_uuid, data in kids_data.items()
        },
        const.DATA_CHORES: {
            str(chore_uuid): str(data.get(const.DATA_CHORE_NAME, chore_uuid))
            for chore_uuid, data in chores_data.items()
        },
        const.DATA_REWARDS: {
            str(reward_uuid): str(data.get(const.DATA_REWARD_NAME, reward_uuid))
            for reward_uuid, data in rewards_data.items()
        },
        const.DATA_PARENTS: {
            str(parent_uuid): str(data.get(const.DATA_PARENT_NAME, parent_uuid))
            for parent_uuid, data in parents_data.items()
        },
        const.DATA_BONUSES: {
            str(bonus_uuid): str(data.get(const.DATA_BONUS_NAME, bonus_uuid))
            for bonus_uuid, data in bonuses_data.items()
        },
        const.DATA_PENALTIES: {
            str(penalty_uuid): str(data.get(const.DATA_PENALTY_NAME, penalty_uuid))
            for penalty_uuid, data in penalties_data.items()
        },
    }


def _resolve_reference_name(
    id_map: dict[str, dict[str, str]],
    reference_id: Any,
) -> str | None:
    """Resolve a reference UUID across known item maps."""
    if reference_id is None:
        return None

    ref = str(reference_id)
    for mapping in id_map.values():
        if ref in mapping:
            return mapping[ref]
    return None


def _iter_ledger_entries_in_range(
    kid_info: dict[str, Any],
    start_dt: datetime,
    end_dt: datetime,
) -> list[dict[str, Any]]:
    """Return ledger entries for a kid in the requested datetime range."""
    ledger = kid_info.get(const.DATA_KID_LEDGER, [])
    if not isinstance(ledger, list):
        return []

    entries: list[dict[str, Any]] = []
    for raw_entry in ledger:
        if not isinstance(raw_entry, dict):
            continue

        timestamp = raw_entry.get(const.DATA_LEDGER_TIMESTAMP)
        parsed = _coerce_datetime(timestamp)
        if parsed is None:
            continue

        if start_dt <= parsed <= end_dt:
            entries.append(raw_entry)

    entries.sort(key=lambda entry: str(entry.get(const.DATA_LEDGER_TIMESTAMP, "")))
    return entries


def _build_supplemental_period_rollup(
    kids_data: dict[str, Any],
    kid_ids: list[str],
) -> dict[str, Any]:
    """Build supplemental all-time rollup from period buckets.

    This supplements ledger-first report output for long-range context.
    """
    total_points_earned = 0.0
    total_points_spent = 0.0

    total_chores_approved = 0
    total_chores_claimed = 0
    total_chores_disapproved = 0

    total_rewards_approved = 0
    total_rewards_claimed = 0
    total_rewards_disapproved = 0
    total_rewards_points_spent = 0.0

    for kid_id in kid_ids:
        kid_info = kids_data.get(kid_id, {})

        all_time_points = kid_info.get(const.DATA_KID_POINT_PERIODS, {}).get(
            const.DATA_KID_POINT_PERIODS_ALL_TIME,
            {},
        )
        if isinstance(all_time_points, dict):
            total_points_earned += float(
                all_time_points.get(const.DATA_KID_POINT_PERIOD_POINTS_EARNED, 0.0)
            )
            total_points_spent += float(
                all_time_points.get(const.DATA_KID_POINT_PERIOD_POINTS_SPENT, 0.0)
            )

        all_time_chores = kid_info.get(const.DATA_KID_CHORE_PERIODS, {}).get(
            const.PERIOD_ALL_TIME, {}
        )
        if isinstance(all_time_chores, dict):
            total_chores_approved += int(
                all_time_chores.get(const.DATA_KID_CHORE_DATA_PERIOD_APPROVED, 0)
            )
            total_chores_claimed += int(
                all_time_chores.get(const.DATA_KID_CHORE_DATA_PERIOD_CLAIMED, 0)
            )
            total_chores_disapproved += int(
                all_time_chores.get(const.DATA_KID_CHORE_DATA_PERIOD_DISAPPROVED, 0)
            )

        all_time_rewards = kid_info.get(const.DATA_KID_REWARD_PERIODS, {}).get(
            const.PERIOD_ALL_TIME, {}
        )
        if isinstance(all_time_rewards, dict):
            total_rewards_approved += int(
                all_time_rewards.get(const.DATA_KID_REWARD_DATA_PERIOD_APPROVED, 0)
            )
            total_rewards_claimed += int(
                all_time_rewards.get(const.DATA_KID_REWARD_DATA_PERIOD_CLAIMED, 0)
            )
            total_rewards_disapproved += int(
                all_time_rewards.get(const.DATA_KID_REWARD_DATA_PERIOD_DISAPPROVED, 0)
            )
            total_rewards_points_spent += float(
                all_time_rewards.get(const.DATA_KID_REWARD_DATA_PERIOD_POINTS, 0.0)
            )

    return {
        "points": {
            "all_time_earned": round(total_points_earned, const.DATA_FLOAT_PRECISION),
            "all_time_spent": round(total_points_spent, const.DATA_FLOAT_PRECISION),
            "all_time_net": round(
                total_points_earned - total_points_spent,
                const.DATA_FLOAT_PRECISION,
            ),
        },
        "chores": {
            "all_time_approved": total_chores_approved,
            "all_time_claimed": total_chores_claimed,
            "all_time_disapproved": total_chores_disapproved,
        },
        "rewards": {
            "all_time_approved": total_rewards_approved,
            "all_time_claimed": total_rewards_claimed,
            "all_time_disapproved": total_rewards_disapproved,
            "all_time_points_spent": round(
                total_rewards_points_spent,
                const.DATA_FLOAT_PRECISION,
            ),
        },
    }


def _coerce_datetime(value: str | datetime | None) -> datetime | None:
    """Coerce datetime-like values to timezone-aware UTC datetimes."""
    result: datetime | None = None

    if value is None:
        return result

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    parsed = dt_parse(value)
    if isinstance(parsed, datetime):
        result = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    elif isinstance(parsed, date):
        result = datetime.combine(parsed, time.min, tzinfo=UTC)

    return result


def _render_report_markdown(
    report_title: str | None,
    range_result: ReportRangeResult,
    daily_blocks: list[ReportDailyBlock],
) -> str:
    """Render markdown report from daily aggregate blocks."""
    title = report_title or "KidsChores Activity Report"
    lines = [
        f"# {title}",
        "",
        f"Range: {range_result['start_iso']} → {range_result['end_iso']}",
        "",
    ]

    if not daily_blocks:
        lines.append("No activity found for the selected range.")
        return "\n".join(lines)

    for block in daily_blocks:
        lines.append(block["markdown_section"])
        lines.append("")

    return "\n".join(lines).strip()
