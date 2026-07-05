#!/usr/bin/env python3
"""Vytvoří rodičovský účet (username 'rodic', heslo 'rodic') se dvěma dětmi.

Rodiče se nepřihlašují PINem, ale username/heslem. Účet dostane dvě existující
děti: jedno U8 z pobočky Orlova a jedno U10 z pobočky Dolni Lutyne. Protože
v Dolni Lutyne zatím žádné dítě není, vezme se existující U10 dítě a přeřadí
se na Dolni Lutyne.

Spouštět z kořene projektu (ideálně když neběží zápis z API):

    python scripts/create_parent_rodic.py
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_maker, migrate_schema
from app.models import AgeGroup, Branch, Parent, Student
from app.security import hash_pin

USERNAME = "rodic"
PASSWORD = "rodic"
EMAIL = "rodic@judo.cz"
FIRST_NAME = "Rodič"
LAST_NAME = "Testovací"
PHONE = "+420600000000"


async def _branch(session, name: str) -> Branch:
    branch = (await session.execute(select(Branch).where(Branch.name == name))).scalar_one_or_none()
    if branch is None:
        print(f'Pobočka "{name}" nenalezena.', file=sys.stderr)
        sys.exit(1)
    return branch


async def main() -> None:
    await migrate_schema()

    async with async_session_maker() as session:
        async with session.begin():
            orlova = await _branch(session, "Orlova")
            lutyne = await _branch(session, "Dolni Lutyne")

            u8 = (
                await session.execute(
                    select(Student)
                    .join(Student.branches)
                    .where(Student.age_group == AgeGroup.U8, Branch.id == orlova.id)
                    .options(selectinload(Student.branches))
                    .order_by(Student.id)
                    .limit(1),
                )
            ).scalars().first()
            if u8 is None:
                print("Nenašlo se žádné U8 dítě na pobočce Orlova.", file=sys.stderr)
                sys.exit(1)

            u10 = (
                await session.execute(
                    select(Student)
                    .where(Student.age_group == AgeGroup.U10)
                    .options(selectinload(Student.branches))
                    .order_by(Student.id)
                    .limit(1),
                )
            ).scalars().first()
            if u10 is None:
                print("Nenašlo se žádné U10 dítě.", file=sys.stderr)
                sys.exit(1)

            # V Dolni Lutyne zatím žádné dítě není -> přeřadíme U10 dítě na Lutyne.
            u10.branches = [lutyne]

            parent = (
                await session.execute(
                    select(Parent)
                    .where(Parent.username == USERNAME)
                    .options(selectinload(Parent.children)),
                )
            ).scalar_one_or_none()
            if parent is None:
                parent = (
                    await session.execute(
                        select(Parent)
                        .where(Parent.email == EMAIL)
                        .options(selectinload(Parent.children)),
                    )
                ).scalar_one_or_none()
            if parent is None:
                parent = Parent(
                    first_name=FIRST_NAME,
                    last_name=LAST_NAME,
                    email=EMAIL,
                    phone=PHONE,
                )
                session.add(parent)

            parent.username = USERNAME
            parent.password_hash = hash_pin(PASSWORD)
            parent.children = [u8, u10]

        await session.refresh(parent, attribute_names=["children"])
        print(
            f"Hotovo: rodič username={USERNAME!r} heslo={PASSWORD!r} (id={parent.id})\n"
            f"  dítě U8 (Orlova): id={u8.id} {u8.first_name} {u8.last_name}\n"
            f"  dítě U10 (Dolni Lutyne): id={u10.id} {u10.first_name} {u10.last_name}",
        )


if __name__ == "__main__":
    asyncio.run(main())
