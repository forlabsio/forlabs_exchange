from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.order import Order, OrderSide, OrderType, OrderStatus
from app.schemas.order import PlaceOrderRequest
from app.services.matching_engine import try_fill_order

router = APIRouter(prefix="/api/orders", tags=["orders"])

@router.post("")
async def place_order(
    body: PlaceOrderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.type == "limit" and not body.price:
        raise HTTPException(400, "Price required for limit orders")

    order = Order(
        user_id=user.id,
        pair=body.pair,
        side=OrderSide(body.side),
        type=OrderType(body.type),
        price=body.price,
        quantity=body.quantity,
    )
    db.add(order)
    await db.flush()

    result = await try_fill_order(db, order)
    return {"order_id": order.id, "status": order.status.value, "fill_result": result}

@router.delete("/{order_id}")
async def cancel_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    order = await db.get(Order, order_id)
    if not order or order.user_id != user.id:
        raise HTTPException(404, "Order not found")
    if order.status != OrderStatus.open:
        raise HTTPException(400, "Order cannot be cancelled")
    order.status = OrderStatus.cancelled
    await db.commit()
    return {"message": "cancelled"}

@router.get("/open")
async def get_open_orders(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    orders = await db.scalars(
        select(Order).where(Order.user_id == user.id, Order.status == OrderStatus.open)
    )
    return [{"id": o.id, "pair": o.pair, "side": o.side, "type": o.type,
             "price": str(o.price), "quantity": str(o.quantity)} for o in orders]

@router.get("/history")
async def get_order_history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    orders = await db.scalars(
        select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc()).limit(100)
    )
    return [{"id": o.id, "pair": o.pair, "side": o.side, "type": o.type,
             "price": str(o.price), "quantity": str(o.quantity), "status": o.status} for o in orders]
