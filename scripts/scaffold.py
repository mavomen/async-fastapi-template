#!/usr/bin/env python3
"""Interactive CLI scaffold tool - generates model, endpoint, and test boilerplate."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "app" / "models"
SCHEMAS_DIR = ROOT / "app" / "schemas"
CRUD_DIR = ROOT / "app" / "crud"
ENDPOINTS_DIR = ROOT / "app" / "api" / "endpoints"
TESTS_DIR = ROOT / "tests" / "api"


def to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def to_camel(name: str) -> str:
    """Convert snake_case to CamelCase."""
    return "".join(word.capitalize() for word in name.split("_"))


def prompt(prompt_text: str, default: str | None = None) -> str:
    """Prompt user with a default value."""
    tail = f" [{default}]" if default else ""
    value = input(f"{prompt_text}{tail}: ").strip()
    return value or (default or "")


def main():
    print("\n FastAPI Scaffolder\n")

    model_name = prompt("Model name (CamelCase, e.g. Product)", "Product")
    table_name = prompt("Table name (snake_case)", to_snake(model_name) + "s")
    endpoint_prefix = prompt("Endpoint prefix (e.g. products)", to_snake(model_name) + "s")
    fields = prompt("Fields (comma-separated name:type, e.g. title:str,price:float)", "title:str")

    # Parse fields
    field_defs = []
    for field in fields.split(","):
        name, typ = field.strip().split(":")
        field_defs.append((name.strip(), typ.strip()))

    snake = to_snake(model_name)
    camel = to_camel(model_name)

    # ------------------ Model ------------------
    model_code = f'''"""Database model for {camel}."""

from sqlalchemy import String, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class {camel}(BaseModel):
    """Represents a {camel} entity."""

    __tablename__ = "{table_name}"

'''
    for fname, ftype in field_defs:
        if ftype == "str":
            col = "String(255), nullable=False"
            py_type = "str"
        elif ftype == "float":
            col = "Float, nullable=False"
            py_type = "float"
        elif ftype == "int":
            col = "Integer, nullable=False"
            py_type = "int"
        else:
            col = "String(255), nullable=False"
            py_type = "str"
        model_code += f"    {fname}: Mapped[{py_type}] = mapped_column({col})\n"

    model_code += f"""
    def __repr__(self) -> str:
        return f"<{camel}(id={{self.id}})>"
"""
    (MODELS_DIR / f"{snake}.py").write_text(model_code)
    print(f"  Model: {MODELS_DIR / f'{snake}.py'}")

    # ------------------ Schema ------------------
    schema_code = f'''"""Pydantic schemas for {camel}."""

from pydantic import BaseModel, ConfigDict


class {camel}Create(BaseModel):
    """Schema for creating a {camel}."""
'''
    for fname, ftype in field_defs:
        if ftype == "str":
            py_type = "str"
        elif ftype == "float":
            py_type = "float"
        else:
            py_type = "str"
        schema_code += f"    {fname}: {py_type}\n"

    schema_code += f'''
class {camel}Update(BaseModel):
    """Schema for updating a {camel}."""
'''
    for fname, ftype in field_defs:
        if ftype == "str":
            py_type = "str | None"
        elif ftype == "float":
            py_type = "float | None"
        else:
            py_type = "str | None"
        schema_code += f"    {fname}: {py_type} = None\n"

    schema_code += f'''
class {camel}Response(BaseModel):
    """Schema for {camel} response."""
    id: int
'''
    for fname, ftype in field_defs:
        if ftype == "str":
            py_type = "str"
        elif ftype == "float":
            py_type = "float"
        else:
            py_type = "str"
        schema_code += f"    {fname}: {py_type}\n"

    schema_code += "    model_config = ConfigDict(from_attributes=True)\n"
    (SCHEMAS_DIR / f"{snake}.py").write_text(schema_code)
    print(f"  Schema: {SCHEMAS_DIR / f'{snake}.py'}")

    # ------------------ CRUD ------------------
    crud_code = f'''"""CRUD operations for {camel}."""

from app.crud.base import CRUDBase
from app.models.{snake} import {camel}
from app.schemas.{snake} import {camel}Create, {camel}Update


class CRUD{camel}(CRUDBase[{camel}, {camel}Create, {camel}Update]):
    """CRUD operations for {camel}."""

    pass  # extend with custom queries if needed


{snake} = CRUD{camel}({camel})
'''
    (CRUD_DIR / f"{snake}.py").write_text(crud_code)
    print(f"  CRUD: {CRUD_DIR / f'{snake}.py'}")

    # ------------------ Endpoint ------------------
    endpoint_code = f'''"""{camel} management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.crud.{snake} import {snake} as crud
from app.schemas.{snake} import {camel}Create, {camel}Update, {camel}Response

router = APIRouter()


@router.get("/", response_model=list[{camel}Response])
async def list_{snake}(
    db: AsyncSession = Depends(get_db),
) -> list[{camel}]:
    """List all {snake}."""
    return await crud.get_multi(db)


@router.post("/", response_model={camel}Response, status_code=201)
async def create_{snake}(
    obj_in: {camel}Create,
    db: AsyncSession = Depends(get_db),
) -> {camel}:
    """Create a new {snake}."""
    return await crud.create(db, obj_in=obj_in)


@router.get("/{{id}}", response_model={camel}Response)
async def get_{snake}(
    id: int,
    db: AsyncSession = Depends(get_db),
) -> {camel}:
    """Get a single {snake} by ID."""
    obj = await crud.get(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="{camel} not found")
    return obj


@router.patch("/{{id}}", response_model={camel}Response)
async def update_{snake}(
    id: int,
    obj_in: {camel}Update,
    db: AsyncSession = Depends(get_db),
) -> {camel}:
    """Update a {snake}."""
    obj = await crud.get(db, id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="{camel} not found")
    return await crud.update(db, db_obj=obj, obj_in=obj_in)


@router.delete("/{{id}}")
async def delete_{snake}(
    id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a {snake}."""
    await crud.delete(db, id=id)
    return {{"detail": "{camel} deleted"}}
'''
    (ENDPOINTS_DIR / f"{snake}.py").write_text(endpoint_code)
    print(f"  Endpoint: {ENDPOINTS_DIR / f'{snake}.py'}")

    # ------------------ Test ------------------
    test_code = f'''"""Tests for {camel} endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_{snake}(async_client: AsyncClient):
    """Create a new {snake}."""
    payload = {{"title": "Test"}}
    resp = await async_client.post("/api/v1/{endpoint_prefix}/", json=payload)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_list_{snake}(async_client: AsyncClient):
    """List {snake}."""
    resp = await async_client.get("/api/v1/{endpoint_prefix}/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
'''
    (TESTS_DIR / f"test_{snake}.py").write_text(test_code)
    print(f"  Test: {TESTS_DIR / f'test_{snake}.py'}")

    print("\n Scaffolding complete! Next steps:")
    print("  1. Register the router in app/api/__init__.py")
    print(f"  2. Create Alembic migration for {table_name}")
    print("  3. Run 'make dev' and test your new endpoint!\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n Cancelled.")
        sys.exit(0)
