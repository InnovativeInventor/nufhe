import numpy

import reikna.helpers as helpers
from reikna.cluda import dtypes, Module, functions
from reikna.core import Computation, Parameter, Annotation, Type, Transformation


TEMPLATE = helpers.template_for(__file__)


def fft_transform_ref(data, inverse=False, i32_conversion=False):
    if i32_conversion and not inverse:
        N = data.shape[-1]
    else:
        N = data.shape[-1] * 2

    batch_shape = data.shape[:-1]
    data = data.reshape(numpy.prod(batch_shape), data.shape[-1])

    coeffs = numpy.exp(-2j * numpy.pi * numpy.arange(N // 2) / N / 2)

    f64_to_i32 = lambda x: numpy.round(x).astype(numpy.int64).astype(numpy.int32)

    if inverse:
        final_shape = batch_shape + ((N,) if i32_conversion else (N // 2,))
        res = numpy.fft.ifft(data).conj() * coeffs
        if i32_conversion:
            res = numpy.concatenate([
                f64_to_i32(res.real),
                f64_to_i32(res.imag)], axis=1)
        return res.reshape(final_shape)
    else:
        if i32_conversion:
            data = (data[:,:N//2] - 1j * data[:,N//2:])
        return numpy.fft.fft(data * coeffs).reshape(batch_shape + (N // 2,))


def fft_transformed_add_ref(data1, data2):
    return data1 + data2


def fft_transformed_mul_ref(data1, data2):
    return data1 * data2


class FFT512:

    def __init__(self, module):
        self.module = module

        self.transform_length = 512
        self.elem_dtype = numpy.dtype('complex128')
        self.elem_ctype = dtypes.ctype(self.elem_dtype)

        self.polynomial_length = 1024
        self.polynomial_dtype = numpy.int32
        self.polynomial_ctype = dtypes.ctype(self.polynomial_dtype)

        self.threads_per_transform = 64
        self.temp_dtype = numpy.dtype('float64')
        self.temp_ctype = dtypes.ctype(self.temp_dtype)
        self.temp_length = 576

        twd_fw = numpy.empty((8, 72), numpy.complex128)
        twd_inv = numpy.empty((8, 72), numpy.complex128)
        for i in range(8):
            for elem_id in range(64):
                twd_fw[i, elem_id + elem_id//8] = numpy.exp(
                    -2j * numpy.pi / self.transform_length * i * elem_id)
                twd_inv[i, elem_id + elem_id//8] = numpy.exp(
                    2j * numpy.pi / self.transform_length * i * elem_id)

        idxs = numpy.arange(self.polynomial_length // 2)
        coeffs = numpy.exp(-2j * numpy.pi * idxs / self.polynomial_length / 2)

        self.cdata_fw = numpy.concatenate([twd_fw.flatten(), coeffs])
        self.cdata_inv = numpy.concatenate([twd_inv.flatten(), coeffs / self.transform_length])
        self.cdata_fw_ctype = dtypes.ctype(self.cdata_fw.dtype)
        self.cdata_inv_ctype = dtypes.ctype(self.cdata_inv.dtype)

    def __process_modules__(self, process):
        return FFT512(process(self.module))


def fft512():
    module = Module(
        TEMPLATE.get_def('fft512'),
        render_kwds=dict(
            elem_ctype=dtypes.ctype(numpy.complex128),
            temp_ctype=dtypes.ctype(numpy.float64),
            cdata_ctype=dtypes.ctype(numpy.complex128),
            polar_unit=functions.polar_unit(numpy.float64),
            mul=functions.mul(numpy.complex128, numpy.complex128),
            ))
    return FFT512(module)