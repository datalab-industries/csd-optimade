from __future__ import annotations

import datetime
import io
import math
import warnings

import ase.io
import ccdc.crystal
import ccdc.entry
import ccdc.io
from optimade.adapters.structures.ase import from_ase_atoms
from optimade.models import StructureResource


def from_csd_entry_via_cif_and_ase(entry: ccdc.entry.Entry) -> StructureResource:
    cif = entry.crystal.to_string(format="cif")
    warnings.filterwarnings("ignore", category=UserWarning)
    ase_atoms = ase.io.read(io.StringIO(cif), format="cif")
    return StructureResource(
        **{
            "attributes": from_ase_atoms(ase_atoms),
            "id": entry.identifier,
            "type": "structures",
        }
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


def from_csd_entry_directly(entry: ccdc.entry.Entry) -> StructureResource:
    asym_unit = entry.crystal.asymmetric_unit_molecule
    elements = {d.atomic_symbol for d in asym_unit.atoms}
    return StructureResource(
        **{
            "attributes": {
                "last_modified": datetime.datetime.now().isoformat(),
                "chemical_formula_descriptive": asym_unit.formula.replace(" ", ""),
                "chemical_formula_reduced": _reduce_csd_formula(asym_unit.formula),
                "elements": sorted(list(elements)),
                "nelements": len(elements),
                "nsites": len(asym_unit.atoms),
                "species": [
                    {
                        "chemical_symbols": [e],
                        "name": e,
                        "concentration": [1.0],
                    }
                    for e in elements
                ],
                "_csd_lattice_parameters": [
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
                "_csd_deposit_date": entry.deposition_date.isoformat(),
                "species_at_sites": [atom.atomic_symbol for atom in asym_unit.atoms],
                "cartesian_site_positions": [
                    [atom.coordinates.x, atom.coordinates.y, atom.coordinates.z]
                    for atom in asym_unit.atoms
                ],
                "structure_features": [],
            },
            "id": entry.identifier,
            "type": "structures",
        }
    )
