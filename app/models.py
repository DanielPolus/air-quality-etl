from __future__ import annotations

from enum import Enum
from datetime import datetime
from typing import List

from sqlalchemy import (
    String, DateTime, Integer, Float, ForeignKey, func, Enum as SQLEnum,
    UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ParameterEnum(str, Enum):
    pm25 = "pm25"
    pm10 = "pm10"
    no2 = "no2"
    o3 = "o3"


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), default="openaq", nullable=False)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    city: Mapped[str] = mapped_column(String(128), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(256), nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=True)
    lon: Mapped[float] = mapped_column(Float, nullable=True)

    measurements: Mapped[List["Measurement"]] = relationship(
        back_populates="station", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_station_source_extid"),
    )


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    station_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stations.id", ondelete="CASCADE"), index=True, nullable=False
    )

    parameter: Mapped[ParameterEnum] = mapped_column(
        SQLEnum(ParameterEnum, name="parameter_enum"),
        index=True,
        nullable=False
    )

    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)

    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    station: Mapped["Station"] = relationship(back_populates="measurements")

    __table_args__ = (
        UniqueConstraint("station_id", "parameter", "measured_at", name="uq_station_param_time"),
        Index("ix_param_measured_at", "parameter", "measured_at"),
    )
