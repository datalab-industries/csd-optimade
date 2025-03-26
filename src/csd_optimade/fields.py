from optimade import __api_version__
from optimade.models.baseinfo import BaseInfoAttributes, BaseInfoResource

from csd_optimade import __version__


def generate_csd_provider_fields():
    return {
        "structures": [
            {
                "name": "_csd_chemical_name",
                "type": "string",
                "description": "The name of the chemical as given in the CSD.",
            },
            {
                "name": "_csd_cell_volume",
                "type": "float",
                "description": "The volume of the unit cell in cubic angstroms.",
                "unit": "angstrom^3",  # TODO: check this against latest schema
            },
            {
                "name": "_csd_lattice_parameter_a",
                "type": "float",
                "description": "The a lattice parameter in angstroms.",
                "unit": "angstrom",
            },
            {
                "name": "_csd_lattice_parameter_b",
                "type": "float",
                "description": "The b lattice parameter in angstroms.",
                "unit": "angstrom",
            },
            {
                "name": "_csd_lattice_parameter_c",
                "type": "float",
                "description": "The c lattice parameter in angstroms.",
                "unit": "angstrom",
            },
            {
                "name": "_csd_lattice_parameter_alpha",
                "type": "float",
                "description": "The alpha lattice parameter in degrees.",
            },
            {
                "name": "_csd_lattice_parameter_beta",
                "type": "float",
                "description": "The beta lattice parameter in degrees.",
            },
            {
                "name": "_csd_lattice_parameter_gamma",
                "type": "float",
                "description": "The gamma lattice parameter in degrees.",
            },
            {
                "name": "_csd_crystal_system",
                "type": "string",
                "description": "The crystal system of the structure.",
            },
            {
                "name": "_csd_deposition_date",
                "type": "timestamp",
                "description": "The date the structure was deposited.",
            },
            {
                "name": "_csd_disorder_details",
                "type": "string",
                "description": "Human-readable details of any disorder in the structure.",
            },
            {
                "name": "_csd_ccdc_number",
                "type": "integer",
                "description": "The CCDC deposition ID.",
            },
            {
                "name": "_csd_space_group_symbol_hermann_mauginn",
                "type": "string",
                "description": "The space group symbol for the crystal, following the Hermann-Mauguin notation.",
            },
            {
                "name": "_csd_inchi",
                "type": "list",
                "description": "A list of InChI strings for individual components in the structure.",
            },
            {
                "name": "_csd_inchi_key",
                "type": "list",
                "description": "A list of InChIKeys for individual components in the structure.",
            },
            {
                "name": "_csd_smiles",
                "type": "string",
                "description": "A SMILES string computed for the 3D structure.",
            },
            {
                "name": "_csd_z_value",
                "type": "integer",
                "description": "The number of formula units in the unit cell.",
            },
            {
                "name": "_csd_z_prime",
                "type": "float",
                "description": "The number of formula units in the asymmetric unit.",
            },
            {
                "name": "_csd_remarks",
                "type": "string",
                "description": "Free-text remarks about the structure.",
            },
        ]
    }


def generate_csd_provider_info():
    return {
        "prefix": "csd",
        "name": "Cambridge Structural Database",
        "description": f"A database of crystal structures curated by the Cambridge Crystallographic Data Centre. Licensing and reuse agreements can be found at {generate_license_link()}.",
        "homepage": "https://www.ccdc.cam.ac.uk",
    }


def generate_implementation_info():
    return {
        "name": "CSD OPTIMADE",
        "version": __version__,
        "source_url": "https://github.com/datalab-industries/csd-optimade",
        "issue_tracker": "https://github.com/datalab-industries/csd-optimade",
        "homepage": "https://github.com/datalab-industries/csd-optimade",
    }


def generate_license_link():
    return "https://www.ccdc.cam.ac.uk/licence-agreement"


def generate_csd_info_endpoint() -> dict[str, BaseInfoResource]:
    return {
        "data": BaseInfoResource(
            attributes=BaseInfoAttributes(
                api_version=__api_version__,
                available_api_versions=[],
                formats=["json"],
                available_endpoints=["info", "structures", "references"],
                entry_types_by_format={"json": ["info", "structures", "references"]},
                is_index=False,
                license={"href": generate_license_link()},
                available_licenses=None,
            )
        )
    }
