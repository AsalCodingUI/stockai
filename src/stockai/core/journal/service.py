import logging
from datetime import datetime
from typing import Any

import pytz

from stockai.data.database import session_scope
from stockai.data.models import TradePlan, TradeOutcome

JAKARTA_TZ = pytz.timezone("Asia/Jakarta")
logger = logging.getLogger(__name__)

_instance: "JournalService | None" = None


def get_journal_service() -> "JournalService":
    global _instance
    if _instance is None:
        _instance = JournalService()
    return _instance


class JournalService:
    def create_plan(self, *, symbol: str, tujuan: str, modal: float,
                    entry_low: float, entry_high: float, stop_loss: float,
                    tp1: float, tp2: float | None = None, tp3: float | None = None,
                    notes: str | None = None, ai_summary: str | None = None) -> dict:
        """Create a new trade plan. Returns plan as dict."""
        # Calculate risk_reward from tp1
        risk = ((entry_low + entry_high) / 2) - stop_loss
        reward = tp1 - ((entry_low + entry_high) / 2)
        rr = round(reward / risk, 2) if risk > 0 else 0.0

        with session_scope() as sess:
            plan = TradePlan(
                symbol=symbol.upper().strip(),
                tujuan=tujuan,
                modal=modal,
                entry_low=entry_low,
                entry_high=entry_high,
                stop_loss=stop_loss,
                tp1=tp1, tp2=tp2, tp3=tp3,
                risk_reward=rr,
                notes=notes,
                ai_summary=ai_summary,
                status="OPEN",
            )
            sess.add(plan)
            sess.flush()
            return self._plan_to_dict(plan)

    def get_plan(self, plan_id: int) -> dict | None:
        """Get plan by id."""
        with session_scope() as sess:
            plan = sess.get(TradePlan, plan_id)
            if not plan:
                return None
            return self._plan_to_dict(plan)

    def list_plans(self, symbol: str | None = None, status: str | None = None,
                   limit: int = 50) -> list[dict]:
        """List plans, optionally filtered by symbol/status."""
        with session_scope() as sess:
            q = sess.query(TradePlan)
            if symbol:
                q = q.filter(TradePlan.symbol == symbol.upper().strip())
            if status:
                q = q.filter(TradePlan.status == status.upper())
            plans = q.order_by(TradePlan.created_at.desc()).limit(limit).all()
            return [self._plan_to_dict(p) for p in plans]

    def cancel_plan(self, plan_id: int) -> bool:
        """Cancel an open plan."""
        with session_scope() as sess:
            plan = sess.get(TradePlan, plan_id)
            if not plan or plan.status != "OPEN":
                return False
            plan.status = "CANCELLED"
            plan.updated_at = datetime.utcnow()
            return True

    def check_outcome(self, plan_id: int, current_price: float) -> dict:
        """Check current price against plan TP/SL. Updates status if terminal hit.
        Returns outcome dict with: outcome, pnl_pct, message."""
        with session_scope() as sess:
            plan = sess.get(TradePlan, plan_id)
            if not plan:
                return {"outcome": "NOT_FOUND", "pnl_pct": None, "message": "Plan not found"}

            entry_mid = (plan.entry_low + plan.entry_high) / 2
            outcome = "OPEN"
            pnl_pct = None

            if current_price <= plan.stop_loss:
                outcome = "SL_HIT"
                pnl_pct = round((current_price / entry_mid - 1) * 100, 2)
            elif plan.tp3 and current_price >= plan.tp3:
                outcome = "TP3_HIT"
                pnl_pct = round((plan.tp3 / entry_mid - 1) * 100, 2)
            elif plan.tp2 and current_price >= plan.tp2:
                outcome = "TP2_HIT"
                pnl_pct = round((plan.tp2 / entry_mid - 1) * 100, 2)
            elif current_price >= plan.tp1:
                outcome = "TP1_HIT"
                pnl_pct = round((plan.tp1 / entry_mid - 1) * 100, 2)
            elif plan.entry_low <= current_price <= plan.entry_high:
                outcome = "ENTRY_ZONE"

            # Record outcome row
            record = TradeOutcome(
                plan_id=plan_id,
                price_at_check=current_price,
                outcome=outcome,
                pnl_pct=pnl_pct,
            )
            sess.add(record)

            # Close plan if terminal outcome
            terminal = {"SL_HIT", "TP1_HIT", "TP2_HIT", "TP3_HIT"}
            if outcome in terminal and plan.status == "OPEN":
                plan.status = outcome
                plan.exit_price = current_price
                plan.exit_date = datetime.utcnow()
                plan.pnl_pct = pnl_pct
                plan.days_held = (datetime.utcnow() - plan.created_at).days
                plan.updated_at = datetime.utcnow()

            return {"outcome": outcome, "pnl_pct": pnl_pct,
                    "message": f"{outcome} @ Rp {current_price:,.0f}"}

    def get_stats(self) -> dict:
        """Get journal stats: win_rate, total, by_status, avg_pnl."""
        with session_scope() as sess:
            all_plans = sess.query(TradePlan).all()
            total = len(all_plans)
            open_count = sum(1 for p in all_plans if p.status == "OPEN")
            closed = [p for p in all_plans if p.status not in ("OPEN", "CANCELLED")]
            wins = [p for p in closed if p.status in ("TP1_HIT", "TP2_HIT", "TP3_HIT")]
            losses = [p for p in closed if p.status == "SL_HIT"]
            win_rate = round(len(wins) / len(closed) * 100, 1) if closed else 0.0
            avg_pnl = round(
                sum(p.pnl_pct for p in closed if p.pnl_pct is not None) / len(closed), 2
            ) if closed else 0.0

            return {
                "total": total,
                "open": open_count,
                "closed": len(closed),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": win_rate,
                "avg_pnl_pct": avg_pnl,
                "by_symbol": self._stats_by_symbol(closed),
            }

    def check_all_open_plans(self) -> list[dict]:
        """Fetch current prices for all OPEN plans, check outcomes. Used by scheduler."""
        from stockai.data.sources.yahoo import YahooFinanceSource
        yahoo = YahooFinanceSource()

        with session_scope() as sess:
            open_plans = sess.query(TradePlan).filter(TradePlan.status == "OPEN").all()
            plan_ids = [p.id for p in open_plans]

        results = []
        for pid in plan_ids:
            plan_dict = self.get_plan(pid)
            if not plan_dict:
                continue
            symbol = plan_dict["symbol"]
            try:
                info = yahoo.get_stock_info(symbol)
                price = info.get("current_price") or info.get("previousClose")
                if price:
                    outcome = self.check_outcome(pid, float(price))
                    results.append({"plan_id": pid, "symbol": symbol,
                                   "price": price, **outcome})
            except Exception as e:
                logger.warning("Failed to check plan %d (%s): %s", pid, symbol, e)

        return results

    def _stats_by_symbol(self, closed_plans: list) -> dict:
        stats: dict[str, dict] = {}
        for p in closed_plans:
            s = p.symbol
            if s not in stats:
                stats[s] = {"total": 0, "wins": 0, "losses": 0}
            stats[s]["total"] += 1
            if p.status in ("TP1_HIT", "TP2_HIT", "TP3_HIT"):
                stats[s]["wins"] += 1
            elif p.status == "SL_HIT":
                stats[s]["losses"] += 1
        return stats

    def _plan_to_dict(self, plan: TradePlan) -> dict:
        return {
            "id": plan.id,
            "symbol": plan.symbol,
            "tujuan": plan.tujuan,
            "modal": plan.modal,
            "entry_low": plan.entry_low,
            "entry_high": plan.entry_high,
            "stop_loss": plan.stop_loss,
            "tp1": plan.tp1,
            "tp2": plan.tp2,
            "tp3": plan.tp3,
            "risk_reward": plan.risk_reward,
            "status": plan.status,
            "notes": plan.notes,
            "ai_summary": plan.ai_summary,
            "entry_price_actual": plan.entry_price_actual,
            "exit_price": plan.exit_price,
            "exit_date": plan.exit_date.isoformat() if plan.exit_date else None,
            "pnl_pct": plan.pnl_pct,
            "days_held": plan.days_held,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        }
