"""Algorithm registry used by the CLI dispatcher."""

from normal_blobs.algorithms import (
    brush_stroke_cells,
    center_average_normalization,
    edge_gradient_cascade,
    voronoi_flow_cells,
)
from normal_blobs.models import AlgorithmSpec


ALGORITHMS = {
    module.NAME: AlgorithmSpec(
        name=module.NAME,
        summary=module.SUMMARY,
        description=module.DESCRIPTION,
        help_epilog=module.HELP_EPILOG,
        add_arguments=module.add_arguments,
        make_config=module.make_config,
        process=module.process,
        estimate_resources=module.estimate_resources,
    )
    for module in (
        center_average_normalization,
        edge_gradient_cascade,
        voronoi_flow_cells,
        brush_stroke_cells,
    )
}
