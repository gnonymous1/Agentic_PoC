"""
SQLAlchemy Models for AgentOS
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from database import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    sessions = relationship("Session", back_populates="user")
    synthesis_plans = relationship("SynthesisPlan", back_populates="user")
    code_modifications = relationship("CodeModification", back_populates="user")
    memory_episodes = relationship("MemoryEpisode", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="sessions")


class SynthesisPlan(Base):
    __tablename__ = "synthesis_plans"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    plan_data = Column(JSON, nullable=False)
    status = Column(String, index=True, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="synthesis_plans")


class CodeModification(Base):
    __tablename__ = "code_modifications"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    file_path = Column(String, nullable=False)
    modification_type = Column(String, nullable=False)
    old_content = Column(Text, nullable=True)
    new_content = Column(Text, nullable=True)
    applied = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    applied_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="code_modifications")


class MemoryEpisode(Base):
    __tablename__ = "memory_episodes"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"))
    content = Column(Text, nullable=False)
    layer = Column(String, index=True, nullable=False)
    metadata_ = Column("metadata", JSON, nullable=True)  # metadata is reserved in SQLAlchemy
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="memory_episodes")
