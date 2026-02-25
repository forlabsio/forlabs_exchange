from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class PaymentHistory(Base):
    __tablename__ = "payment_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    tx_hash = Column(String, unique=True, nullable=False, index=True)
    amount = Column(Numeric(18, 6), nullable=False)
    network = Column(String(20), default="polygon")
    verified_at = Column(DateTime(timezone=True), server_default=func.now())
