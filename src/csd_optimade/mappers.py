from __future__ import annotations

import io
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


def from_csd_entry_directly(entry: ccdc.entry.Entry) -> StructureResource:
    return StructureResource(
        **{
            "attributes": {
                "chemical_formula_descriptive": entry.molecule.formula,
                "chemical_formula_reduced": entry.molecule.formula,
                "elements": list(entry.molecule.formula),
                "nelements": len(entry.molecule.formula),
                "nperiodic_sites": len(entry.molecule.atoms),
                "species": [
                    {
                        "chemical_symbols": [atom.atomic_symbol],
                        "name": atom.atomic_symbol,
                    }
                    for atom in entry.molecule.atoms
                ],
                "lattice_vectors": [
                    [entry.cell.a, 0, 0],
                    [0, entry.cell.b, 0],
                    [0, 0, entry.cell.c],
                ],
                "cartesian_site_positions": [
                    [atom.x, atom.y, atom.z] for atom in entry.molecule.atoms
                ],
                "nsites": len(entry.molecule.atoms),
                "nspecies": len({atom.atomic_symbol for atom in entry.molecule.atoms}),
            },
            "id": entry.identifier,
            "type": "structures",
        }
    )
