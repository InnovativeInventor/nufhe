import numpy

from reikna.algorithms import PureParallel
from reikna.core import Computation, Transformation, Parameter, Annotation, Type
from reikna.cluda import dtypes

from .numeric_functions import Torus32


class ModSwitchFromTorus32(Computation):

    def __init__(self, phase_arr):
        out_arr = Type(numpy.int32, phase_arr.shape)
        tr = Transformation(
            [
                Parameter('output', Annotation(out_arr, 'o')),
                Parameter('phase', Annotation(phase_arr, 'i')),
                Parameter('Msize', Annotation(Type(numpy.int32))),
            ],
            """
            ${Torus32} phase = ${phase.load_same};
            ${uint64} interv = ((((${uint64})1) << 63) / ${Msize}) * 2;
            ${uint64} half_interval = interv / 2;
            ${uint64} phase64 = (((${uint64})phase) << 32) + half_interval;
            ${output.store_same}(phase64 / interv);
            """,
            render_kwds=dict(
                Torus32=dtypes.ctype(Torus32),
                uint64=dtypes.ctype(numpy.uint64)),
            connectors=['output', 'phase'])

        self._pp = PureParallel.from_trf(tr, guiding_array='output')

        Computation.__init__(self, [
            Parameter('output', Annotation(self._pp.parameter.output, 'o')),
            Parameter('phase', Annotation(self._pp.parameter.phase, 'i')),
            Parameter('Msize', Annotation(self._pp.parameter.Msize))])

    def _build_plan(self, plan_factory, device_params, output, input_):
        plan = plan_factory()
        plan.computation_call(self._pp, output, ais, input_)
        return plan