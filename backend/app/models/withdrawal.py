from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class WithdrawalStatus:
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    completed = "completed"


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(18, 6), nullable=False)
    to_address = Column(String, nullable=False)
    network = Column(String(20), default="polygon")
    status = Column(String(20), default=WithdrawalStatus.pending)
    tx_hash = Column(String, nullable=True)
    admin_note = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
