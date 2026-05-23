from __future__ import annotations

import json
import sqlite3
import csv
from pathlib import Path

from .models import SetupCandidate, Trade


class Journal:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self._batch_depth = 0
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def begin_batch(self) -> None:
        if self._batch_depth == 0:
            self.conn.execute("begin")
        self._batch_depth += 1

    def end_batch(self) -> None:
        if self._batch_depth == 0:
            return
        self._batch_depth -= 1
        if self._batch_depth == 0:
            self.conn.commit()

    def reset(self) -> None:
        self.conn.executescript(
            """
            delete from trades;
            delete from candidates;
            """
        )
        self._commit_unless_batching()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            create table if not exists candidates (
                id text primary key,
                created_at text not null,
                symbol text not null,
                direction text not null,
                setup_type text not null,
                confidence real not null,
                status text not null,
                rejection_reason text,
                entry_low real not null,
                entry_high real not null,
                stop_loss real not null,
                take_profits text not null,
                confluences text not null,
                risks text not null
            );

            create table if not exists trades (
                candidate_id text primary key,
                symbol text not null,
                direction text not null,
                opened_at text not null,
                entry real not null,
                stop_loss real not null,
                take_profits text not null,
                size_units real not null,
                risk_amount real not null,
                closed_at text,
                exit_price real,
                exit_reason text,
                pnl real
            );
            """
        )
        self._commit_unless_batching()

    def save_candidate(self, candidate: SetupCandidate) -> None:
        self.conn.execute(
            """
            insert or replace into candidates values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.id,
                candidate.created_at.isoformat(),
                candidate.symbol,
                candidate.direction.value,
                candidate.setup_type,
                candidate.confidence,
                candidate.status.value,
                candidate.rejection_reason,
                candidate.entry_low,
                candidate.entry_high,
                candidate.stop_loss,
                json.dumps(candidate.take_profits),
                json.dumps(candidate.confluences),
                json.dumps(candidate.risks),
            ),
        )
        self._commit_unless_batching()

    def _commit_unless_batching(self) -> None:
        if self._batch_depth == 0:
            self.conn.commit()

    def save_trade(self, trade: Trade) -> None:
        self.conn.execute(
            """
            insert or replace into trades values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.candidate_id,
                trade.symbol,
                trade.direction.value,
                trade.opened_at.isoformat(),
                trade.entry,
                trade.stop_loss,
                json.dumps(trade.take_profits),
                trade.size_units,
                trade.risk_amount,
                trade.closed_at.isoformat() if trade.closed_at else None,
                trade.exit_price,
                trade.exit_reason,
                trade.pnl,
            ),
        )
        self._commit_unless_batching()

    def summary(self) -> dict[str, float | int | None]:
        cur = self.conn.cursor()
        candidates = cur.execute("select count(*) from candidates").fetchone()[0]
        executed = cur.execute("select count(*) from trades").fetchone()[0]
        built = cur.execute("select count(*) from candidates where status = 'built'").fetchone()[0]
        rejected = cur.execute("select count(*) from candidates where status = 'rejected'").fetchone()[0]
        expired = cur.execute("select count(*) from candidates where status = 'expired'").fetchone()[0]
        not_executed = rejected + expired
        pnl = cur.execute("select coalesce(sum(pnl), 0) from trades where pnl is not null").fetchone()[0]
        wins = cur.execute("select count(*) from trades where pnl > 0").fetchone()[0]
        closed = cur.execute("select count(*) from trades where pnl is not null").fetchone()[0]
        return {
            "candidates": candidates,
            "built": built,
            "rejected": rejected,
            "expired": expired,
            "not_executed": not_executed,
            "executed": executed,
            "closed": closed,
            "wins": wins,
            "win_rate": round(wins / closed, 4) if closed else None,
            "execution_rate": round(executed / candidates, 4) if candidates else None,
            "pnl": round(pnl, 2),
        }

    def export_csvs(self, output_dir: str | Path) -> dict[str, str]:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths = {
            "candidates": out / "candidates.csv",
            "trades": out / "trades.csv",
        }
        self._export_table("candidates", paths["candidates"])
        self._export_table("trades", paths["trades"])
        return {name: str(path) for name, path in paths.items()}

    def _export_table(self, table: str, path: Path) -> None:
        cursor = self.conn.execute(f"select * from {table}")
        columns = [description[0] for description in cursor.description]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(columns)
            writer.writerows(cursor.fetchall())
