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
    import ccdc.molecule

from optimade.models import (
    ReferenceResource,
    ReferenceResourceAttributes,
    Species,
    StructureResource,
    StructureResourceAttributes,
)

NOW = datetime.datetime.now()
NOW = NOW.replace(microsecond=0)

CSD_OPTIMADE_SIDENTIFIER = "csd-optimade-psdi"
"""Identifier to use when reporting `sid` to CCDC services."""


def _get_citations(entry) -> list[ReferenceResource]:
    """Return attached reference resources given the CSD API citation format."""
    citations = []
    for citation in entry.publications:
        # Use the DOI as OPTIMADE identifier, if available, otherwise generate one
        # from first author, year and random string (cannot detect duplicates)
        _id = citation.doi
        if _id is None:
            first_author = citation.authors.split(", ")[0].split(".")[-1].split(" ")[-1]
            _id = f"{first_author}{citation.year}-{''.join(random.choices(string.ascii_lowercase, k=6))}"

        citations.append(
            ReferenceResource(
                id=_id,
                type="references",
                attributes=ReferenceResourceAttributes(
                    last_modified=NOW,
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


def _reduce_csd_formula(formula: str) -> tuple[str, set[str]]:
    """Given a CSD Python API formula string, return a reduced
    OPTIMADE formula and the set of elements* present.

    * including "D"

    Parameters:
        formula: The `Entry.formula` string from the CSD Python API.

    Returns:
        A tuple of the reduced formula and the set of elements present.

    """
    import re

    if "," in formula:
        raise ValueError(f"Cannot reduce multi-component formula: {formula}")

    if not formula:
        raise ValueError("Cannot reduce non-existent formula")

    formula_dct = {}
    # Strip leading numbers
    formula = re.sub(r"^[0-9.]+(.*)$", r"\1", formula)

    for e in formula.strip("(").strip(")n").strip("x(").split(" "):
        matches = re.match(r"([a-zA-Z]+)([0-9]*)", e)
        if matches:
            species, count = matches.groups()
            formula_dct[species] = int(count) if count else 1

    # Elements list should include "D" so that it can be post-filtered in species lists
    elements = set(formula_dct.keys())

    if "D" in formula_dct:
        formula_dct["H"] = formula_dct.get("H", 0) + formula_dct.pop("D")

    reducer = math.gcd(*formula_dct.values())

    formula_str: str = ""
    for e in sorted(formula_dct):
        formula_str += (
            f"{e}{formula_dct[e] // reducer if formula_dct[e] != reducer else ''}"
        )

    if not formula_str:
        raise RuntimeError(f"Unable to create formula for {formula}")

    return formula_str, elements


def from_csd_entry_directly(
    entry: ccdc.entry.Entry,
) -> tuple[StructureResource, list[ReferenceResource]]:
    """Convert a single `ccdc.entry.Entry` into an OPTIMADE structure,
    returning any attached citations as OPTIMADE references.

    """
    asym_unit = entry.crystal.asymmetric_unit_molecule

    dep_date: datetime.datetime | datetime.date | None = entry.deposition_date
    dep_date = (
        datetime.datetime.fromisoformat(dep_date.isoformat()) if dep_date else None
    )

    positions: list | None = None
    lattice_params: list[list[float | None]] = [[None, None, None], [None, None, None]]
    cell_volume: float | None = None
    packed_mol: ccdc.molecule.Molecule | None = None
    if entry.has_3d_structure:
        packed_mol = entry.crystal.packing()
        try:
            positions = [
                [atom.coordinates.x, atom.coordinates.y, atom.coordinates.z]
                for atom in packed_mol.atoms
            ]
            # Handle case that atoms is []
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

    references: list[ReferenceResource] = _get_citations(entry)
    relationships: dict[str, dict] | None = None
    if references:
        relationships = {
            "references": {
                "data": [{"type": "references", "id": ref.id} for ref in references]
            }
        }

    inchis = entry.component_inchis

    structure_features = []
    try:
        reduced_formula, elements = _reduce_csd_formula(entry.formula)
    except ValueError:
        reduced_formula = None
        elements = {d.atomic_symbol for d in asym_unit.atoms}

    except Exception:
        warnings.warn(
            f"Unable to reduce formula for {entry.identifier}: {entry.formula} / {asym_unit.formula}"
        )
        reduced_formula = None

    optimade_elements = elements.copy()
    # Replace deuterium with H
    if "D" in elements:
        optimade_elements.remove("D")
        optimade_elements.add("H")

    optimade_species = [
        Species(
            chemical_symbols=[e if e != "D" else "H"],
            name=e,
            concentration=[1.0],
        )
        for e in elements
    ]

    optimade_species_at_sites: list[str] | None = (
        [atom.atomic_symbol for atom in packed_mol.atoms]
        if (positions and packed_mol)
        else None
    )

    # From CSD docs:
    # > Non standard spacegroup numbers, those above 230, will be returned with setting number 0. Unrecognised spacegroups will raise a RuntimeError.
    try:
        space_group_int_number = entry.crystal.spacegroup_number_and_setting[0]
    except RuntimeError:
        space_group_int_number = None
    if space_group_int_number > 230:
        space_group_int_number = None

    space_group_symbol = entry.crystal.spacegroup_symbol

    if entry.has_disorder:
        structure_features += ["disorder"]

    if optimade_species_at_sites:
        for s in optimade_species:
            if s.name not in optimade_species_at_sites:
                structure_features += ["implicit_atoms"]
                break

    resource = StructureResource(
        **{
            "id": entry.identifier,
            "type": "structures",
            "relationships": relationships,
            "links": {
                "self": f"https://www.ccdc.cam.ac.uk/services/structures?pid=csd:{entry.identifier}&sid={CSD_OPTIMADE_SIDENTIFIER}"
            },
            "attributes": StructureResourceAttributes(
                immutable_id=entry.identifier,
                last_modified=NOW,
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
                species=optimade_species if positions else None,
                species_at_sites=optimade_species_at_sites,
                cartesian_site_positions=positions,
                structure_features=structure_features,
                space_group_int_number=space_group_int_number,
                space_group_symbol_hermann_maugin=space_group_symbol,
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
                _csd_inchi=[inchi.inchi for inchi in inchis] if inchis else None,
                _csd_inchi_key=[inchi.key for inchi in inchis] if inchis else None,
                _csd_smiles=entry.crystal.molecule.smiles,
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
