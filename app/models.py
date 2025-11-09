from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, Integer, Float, ForeignKey, func, Index

class Base(DeclarativeBase):
    pass

class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[int] = mapped_column(Integer, index=True)
    city: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(120))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)

    measurements: Mapped[list["Measurement"]] = relationship(back_populates="station")

class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)
    parameter: Mapped[str] = mapped_column(String(10), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16), default="µg/m³")
    measured_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), index=True, server_default=func.now())

    station: Mapped[Station] = relationship(back_populates="measurements")

Index("ix_param_measured_at", Measurement.parameter, Measurement.measured_at)
