from __future__ import annotations

import datetime
import math
import random
import string
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ccdc.crystal
    import ccdc.entry
    import ccdc.io

from optimade.models import (
    ReferenceResource,
    ReferenceResourceAttributes,
    Species,
    StructureResource,
    StructureResourceAttributes,
)


def _reduce_csd_formula(formula: str) -> str:
    import re

    formula_dct = {}
    for e in formula.strip(")n").split(" "):
        matches = re.match(r"([a-zA-Z]+)([0-9]*)", e)
        if matches:
            species, count = matches.groups()
            formula_dct[species] = int(count) if count else 1

    reducer = math.gcd(*formula_dct.values())

    formula_str: str = ""
    for e in sorted(formula_dct):
        formula_str += (
            f"{e}{formula_dct[e] // reducer if formula_dct[e] != reducer else ''}"
        )

    return formula_str


def from_csd_entry_directly(
    entry: ccdc.entry.Entry,
) -> tuple[StructureResource, list[ReferenceResource]]:
    """Convert a single `ccdc.entry.Entry` into an OPTIMADE structure,
    returning any attached citations as OPTIMADE references.

    """
    asym_unit = entry.crystal.asymmetric_unit_molecule
    elements = {d.atomic_symbol for d in asym_unit.atoms}
    try:
        positions = [
            [atom.coordinates.x, atom.coordinates.y, atom.coordinates.z]
            for atom in asym_unit.atoms
        ]
    except AttributeError:
        positions = None
    now = datetime.datetime.now()
    now = now.replace(microsecond=0)
    dep_date: datetime.datetime | datetime.date | None = entry.deposition_date
    dep_date = (
        datetime.datetime.fromisoformat(dep_date.isoformat()) if dep_date else None
    )

    def _get_citations(entry) -> list[ReferenceResource]:
        citations = []
        for citation in entry.publications:
            # Use the DOI as OPTIMADE identifier, if available, otherwise generate one
            # from first author, year and random string (cannot detect duplicates)
            _id = citation.doi
            if _id is None:
                first_author = (
                    citation.authors.split(", ")[0].split(".")[-1].split(" ")[-1]
                )
                _id = f"{first_author}{citation.year}-{''.join(random.choices(string.ascii_lowercase, k=6))}"

            citations.append(
                ReferenceResource(
                    id=_id,
                    type="references",
                    attributes=ReferenceResourceAttributes(
                        last_modified=now,
                        authors=[
                            {"name": author} for author in citation.authors.split(", ")
                        ],
                        year=str(
                            citation.year
                        ),  # Potential specification bug that this value should be a string
                        journal=citation.journal.full_name,
                        volume=str(citation.volume),
                        pages=str(citation.first_page),
                        doi=citation.doi,
                    ),
                )
            )
        return citations

    references: list[ReferenceResource] = _get_citations(entry)
    relationships: dict[str, dict] | None = None
    if references:
        relationships = {
            "references": {
                "data": [{"type": "references", "id": ref.id} for ref in references]
            }
        }

    inchi = entry.crystal.generate_inchi()
    if not inchi.success:
        inchi = None

    resource = StructureResource(
        **{
            "id": entry.identifier,
            "type": "structures",
            "relationships": relationships,
            "links": {
                "self": f"https://www.ccdc.cam.ac.uk/structures/Search?Ccdcid={entry.identifier}"
            },
            "attributes": StructureResourceAttributes(
                last_modified=now,
                chemical_formula_descriptive=entry.formula,
                chemical_formula_reduced=_reduce_csd_formula(asym_unit.formula),
                elements=sorted(list(elements)),
                dimension_types=(1, 1, 1),
                nperiodic_dimensions=3,
                nelements=len(elements),
                nsites=len(positions) if positions else None,
                species=[
                    Species(chemical_symbols=[e], name=e, concentration=[1.0])
                    for e in elements
                ]
                if positions
                else None,
                cartesian_site_positions=positions,
                species_at_sites=[atom.atomic_symbol for atom in asym_unit.atoms]
                if positions
                else None,
                structure_features=[],
                # Add custom CSD-specific fields
                _csd_lattice_parameters=[
                    [
                        entry.crystal.cell_lengths.a,
                        entry.crystal.cell_lengths.b,
                        entry.crystal.cell_lengths.c,
                    ],
                    [
                        entry.crystal.cell_angles.alpha,
                        entry.crystal.cell_angles.beta,
                        entry.crystal.cell_angles.gamma,
                    ],
                ],
                _csd_space_group_symbol_hermann_mauginn=entry.crystal.spacegroup_symbol,  # Need to double-check if this matches OPTIMADE 1.2 definition
                _csd_inchi=inchi.inchi if inchi else None,
                _csd_inchi_key=inchi.key if inchi else None,
                _csd_smiles=asym_unit.smiles,
                _csd_z_value=entry.crystal.z_value,
                _csd_z_prime=entry.crystal.z_prime,
                _csd_ccdc_number=entry.ccdc_number,
                _csd_deposition_date={"$date": dep_date},
            ),
        }
    )
    return resource, references
