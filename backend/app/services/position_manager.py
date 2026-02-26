import json
from typing import Optional

from app.core.redis import get_redis


class PositionManager:
    """Manages open trading positions with stop-loss, take-profit, and trailing-stop logic.

    Position state is stored in Redis with key format ``pos:{bot_id}:{user_id}``.
    """

    def __init__(self, bot_id: int, user_id: int):
        self.bot_id = bot_id
        self.user_id = user_id
        self.key = f"pos:{bot_id}:{user_id}"

    # ------------------------------------------------------------------
    # Open / Close
    # ------------------------------------------------------------------

    async def open_position(
        self,
        side: str,
        entry_price: float,
        atr: float,
        stop_loss_atr: float,
        take_profit_atr: Optional[float] = None,
        trailing_atr: Optional[float] = None,
    ) -> None:
        """Open a new position, calculating SL/TP levels from ATR multiples."""
        redis = await get_redis()

        if side == "buy":
            sl = entry_price - stop_loss_atr * atr
            tp = (entry_price + take_profit_atr * atr) if take_profit_atr else None
            trailing = (entry_price - trailing_atr * atr) if trailing_atr else None
        else:  # sell
            sl = entry_price + stop_loss_atr * atr
            tp = (entry_price - take_profit_atr * atr) if take_profit_atr else None
            trailing = (entry_price + trailing_atr * atr) if trailing_atr else None

        pos = {
            "side": side,
            "entry": entry_price,
            "stop_loss": sl,
            "take_profit": tp,
            "trailing_stop": trailing,
            "trailing_active": trailing is not None,
            "trailing_atr_mult": trailing_atr,
            "current_atr": atr,
        }
        await redis.set(self.key, json.dumps(pos))

    async def close_position(self) -> None:
        """Delete the position from Redis."""
        redis = await get_redis()
        await redis.delete(self.key)

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    async def get_position(self) -> Optional[dict]:
        """Return the current position dict, or ``None`` if none exists."""
        redis = await get_redis()
        raw = await redis.get(self.key)
        return json.loads(raw) if raw else None

    async def has_position(self) -> bool:
        """Return ``True`` if a position is currently open."""
        redis = await get_redis()
        return await redis.get(self.key) is not None

    # ------------------------------------------------------------------
    # Exit checks
    # ------------------------------------------------------------------

    async def check_exit(self, current_price: float) -> Optional[str]:
        """Check whether the current price triggers an exit condition.

        Returns:
            ``"stop_loss"`` if stop-loss (including trailing) is hit,
            ``"take_profit"`` if take-profit is hit, or ``None``.
        """
        redis = await get_redis()
        raw = await redis.get(self.key)
        if not raw:
            return None

        pos = json.loads(raw)
        side = pos["side"]
        sl = pos["stop_loss"]
        tp = pos["take_profit"]

        # --- Fixed stop-loss ---
        if side == "buy" and current_price <= sl:
            return "stop_loss"
        if side == "sell" and current_price >= sl:
            return "stop_loss"

        # --- Take-profit ---
        if tp is not None:
            if side == "buy" and current_price >= tp:
                return "take_profit"
            if side == "sell" and current_price <= tp:
                return "take_profit"

        # --- Trailing stop ---
        if pos.get("trailing_active") and pos.get("trailing_stop") is not None:
            trailing = pos["trailing_stop"]
            atr_mult = pos.get("trailing_atr_mult", 1.5)
            atr = pos.get("current_atr", 0)

            if side == "buy":
                new_trailing = current_price - atr_mult * atr
                if new_trailing > trailing:
                    # Price moved favourably -- ratchet trailing stop up
                    pos["trailing_stop"] = new_trailing
                    await redis.set(self.key, json.dumps(pos))
                elif current_price <= trailing:
                    return "stop_loss"
            else:  # sell
                new_trailing = current_price + atr_mult * atr
                if new_trailing < trailing:
                    # Price moved favourably -- ratchet trailing stop down
                    pos["trailing_stop"] = new_trailing
                    await redis.set(self.key, json.dumps(pos))
                elif current_price >= trailing:
                    return "stop_loss"

        return None
