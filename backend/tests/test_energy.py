"""
Tests for Energy service.
"""

import pytest

from backend.models.energy import EnergyReadingCreate
from backend.services import energy_service


@pytest.mark.asyncio
async def test_record_energy_reading(db):
    data = EnergyReadingCreate(asset_id="machine-001", company_id="ACME", kwh=25.5)
    reading = await energy_service.record_energy_reading(db, data)
    assert reading.id is not None
    assert reading.co2_kg == pytest.approx(25.5 * energy_service.CO2_KG_PER_KWH, rel=1e-3)
    assert reading.cost_cents == int(25.5 * energy_service.COST_CENTS_PER_KWH)


@pytest.mark.asyncio
async def test_energy_summary_no_data(db):
    summary = await energy_service.get_energy_summary(db, company_id="EMPTY-CO")
    assert summary.total_kwh == 0.0


@pytest.mark.asyncio
async def test_energy_summary_with_data(db):
    company_id = "ENERGY-TEST"
    for kwh in [10.0, 20.0, 30.0]:
        await energy_service.record_energy_reading(
            db, EnergyReadingCreate(asset_id="m-001", company_id=company_id, kwh=kwh)
        )
    summary = await energy_service.get_energy_summary(db, company_id=company_id)
    assert summary.total_kwh == pytest.approx(60.0)
    assert summary.total_co2_kg == pytest.approx(60.0 * energy_service.CO2_KG_PER_KWH, rel=1e-3)


@pytest.mark.asyncio
async def test_generate_recommendations(db):
    company_id = "REC-TEST"
    # Seed high-consumption readings to trigger recommendations
    for _ in range(5):
        await energy_service.record_energy_reading(
            db, EnergyReadingCreate(asset_id="m-001", company_id=company_id, kwh=35.0)
        )
    recs = await energy_service.generate_recommendations(db, company_id=company_id)
    assert len(recs) >= 1
    assert recs[0].potential_saving_pct is not None


@pytest.mark.asyncio
async def test_list_readings(db):
    company_id = "LIST-ENERGY"
    for kwh in [5.0, 10.0, 15.0]:
        await energy_service.record_energy_reading(
            db, EnergyReadingCreate(asset_id="m-list", company_id=company_id, kwh=kwh)
        )
    readings = await energy_service.list_readings(db, company_id=company_id)
    assert len(readings) >= 3
