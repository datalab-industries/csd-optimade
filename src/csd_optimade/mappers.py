from __future__ import annotations

import datetime
import math
import random
import string
import warnings
from typing import TYPE_CHECKING

from optimade.models.utils import anonymize_formula

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

    if "," in formula:
        raise ValueError(f"Cannot reduce multi-component formula: {formula}")

    if not formula:
        raise ValueError("Cannot reduce non-existent formula")

    formula_dct = {}
    for e in formula.strip("(").strip(")n").split(" "):
        matches = re.match(r"([a-zA-Z]+)([0-9]*)", e)
        if matches:
            species, count = matches.groups()
            formula_dct[species] = int(count) if count else 1

    reducer = math.gcd(*formula_dct.values())

    if "D" in formula_dct:
        formula_dct["H"] = formula_dct.get("H", 0) + formula_dct.pop("D")

    formula_str: str = ""
    for e in sorted(formula_dct):
        formula_str += (
            f"{e}{formula_dct[e] // reducer if formula_dct[e] != reducer else ''}"
        )

    if not formula_str:
        raise RuntimeError(f"Unable to create formula for {formula}")

    return formula_str


def from_csd_entry_directly(
    entry: ccdc.entry.Entry,
) -> tuple[StructureResource, list[ReferenceResource]]:
    """Convert a single `ccdc.entry.Entry` into an OPTIMADE structure,
    returning any attached citations as OPTIMADE references.

    """
    asym_unit = entry.crystal.asymmetric_unit_molecule

    elements = {d.atomic_symbol for d in asym_unit.atoms}

    optimade_elements = elements.copy()
    # Replace deuterium with H
    if "D" in elements:
        optimade_elements.remove("D")
        optimade_elements.add("H")

    now = datetime.datetime.now()
    now = now.replace(microsecond=0)
    dep_date: datetime.datetime | datetime.date | None = entry.deposition_date
    dep_date = (
        datetime.datetime.fromisoformat(dep_date.isoformat()) if dep_date else None
    )

    positions: list | None = None
    lattice_params: list[list[float | None]] = [[None, None, None], [None, None, None]]
    cell_volume: float | None = None
    if entry.has_3d_structure:
        try:
            positions = [
                [atom.coordinates.x, atom.coordinates.y, atom.coordinates.z]
                for atom in asym_unit.atoms
            ]
            # Handle case that asym_unit.atoms is []
            if not positions:
                positions = None
        except AttributeError:
            positions = None

        lattice_params = [
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
        ]
        cell_volume = entry.crystal.cell_volume

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

    try:
        reduced_formula = _reduce_csd_formula(entry.formula)
    except ValueError:
        reduced_formula = None
    except RuntimeError:
        warnings.warn(
            f"Unable to reduce formula for {entry.identifier}: {entry.formula} / {asym_unit.formula}"
        )
        reduced_formula = None

    resource = StructureResource(
        **{
            "id": entry.identifier,
            "type": "structures",
            "relationships": relationships,
            "links": {
                "self": f"https://www.ccdc.cam.ac.uk/structures/Search?Ccdcid={entry.identifier}"
            },
            "attributes": StructureResourceAttributes(
                immutable_id=entry.identifier,
                last_modified=now,
                chemical_formula_anonymous=anonymize_formula(reduced_formula)
                if reduced_formula
                else None,
                chemical_formula_descriptive=entry.formula,
                chemical_formula_reduced=reduced_formula,
                elements=sorted(list(optimade_elements)),
                dimension_types=(1, 1, 1),
                nperiodic_dimensions=3,
                nelements=len(optimade_elements),
                nsites=len(positions) if positions else None,
                # Make sure the "D" is remapped to "H" in the species list, but continue using it in the sites list
                species=[
                    Species(
                        chemical_symbols=[e if e != "D" else "H"],
                        name=e,
                        concentration=[1.0],
                    )
                    for e in elements
                ]
                if positions
                else None,
                cartesian_site_positions=positions,
                species_at_sites=[atom.atomic_symbol for atom in asym_unit.atoms]
                if positions
                else None,
                structure_features=["disorder"] if entry.has_disorder else [],
                # Add custom CSD-specific fields
                _csd_lattice_parameter_a=lattice_params[0][0],
                _csd_lattice_parameter_b=lattice_params[0][1],
                _csd_lattice_parameter_c=lattice_params[0][2],
                _csd_lattice_parameter_alpha=lattice_params[1][0],
                _csd_lattice_parameter_beta=lattice_params[1][1],
                _csd_lattice_parameter_gamma=lattice_params[1][2],
                _csd_cell_volume=cell_volume,
                _csd_crystal_system=entry.crystal.crystal_system,
                _csd_space_group_symbol_hermann_mauginn=entry.crystal.spacegroup_symbol,  # Need to double-check if this matches OPTIMADE 1.2 definition
                _csd_chemical_name=entry.chemical_name,
                _csd_inchi=inchi.inchi if inchi else None,
                _csd_inchi_key=inchi.key if inchi else None,
                _csd_smiles=asym_unit.smiles,
                _csd_z_value=entry.crystal.z_value,
                _csd_z_prime=entry.crystal.z_prime,
                _csd_ccdc_number=entry.ccdc_number,
                _csd_deposition_date={"$date": dep_date},
                _csd_disorder_details=entry.disorder_details,
                _csd_remarks=entry.remarks if entry.remarks else None,
            ),
        }
    )
    return resource, references
