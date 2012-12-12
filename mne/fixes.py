"""Compatibility fixes for older version of python, numpy and scipy

If you add content to this file, please give the version of the package
at which the fixe is no longer needed.

# XXX : copied from scikit-learn

"""
# Authors: Emmanuelle Gouillart <emmanuelle.gouillart@normalesup.org>
#          Gael Varoquaux <gael.varoquaux@normalesup.org>
#          Fabian Pedregosa <fpedregosa@acm.org>
#          Lars Buitinck <L.J.Buitinck@uva.nl>
# License: BSD

import collections
from operator import itemgetter
import inspect

import numpy as np
import scipy
from math import ceil, log
from numpy.fft import irfft

try:
    Counter = collections.Counter
except AttributeError:
    class Counter(collections.defaultdict):
        """Partial replacement for Python 2.7 collections.Counter."""
        def __init__(self, iterable=(), **kwargs):
            super(Counter, self).__init__(int, **kwargs)
            self.update(iterable)

        def most_common(self):
            return sorted(self.iteritems(), key=itemgetter(1), reverse=True)

        def update(self, other):
            """Adds counts for elements in other"""
            if isinstance(other, self.__class__):
                for x, n in other.iteritems():
                    self[x] += n
            else:
                for x in other:
                    self[x] += 1


def lsqr(X, y, tol=1e-3):
    import scipy.sparse.linalg as sp_linalg
    from ..utils.extmath import safe_sparse_dot

    if hasattr(sp_linalg, 'lsqr'):
        # scipy 0.8 or greater
        return sp_linalg.lsqr(X, y)
    else:
        n_samples, n_features = X.shape
        if n_samples > n_features:
            coef, _ = sp_linalg.cg(safe_sparse_dot(X.T, X),
                                   safe_sparse_dot(X.T, y),
                                   tol=tol)
        else:
            coef, _ = sp_linalg.cg(safe_sparse_dot(X, X.T), y, tol=tol)
            coef = safe_sparse_dot(X.T, coef)

        residues = y - safe_sparse_dot(X, coef)
        return coef, None, None, residues


def _unique(ar, return_index=False, return_inverse=False):
    """A replacement for the np.unique that appeared in numpy 1.4.

    While np.unique existed long before, keyword return_inverse was
    only added in 1.4.
    """
    try:
        ar = ar.flatten()
    except AttributeError:
        if not return_inverse and not return_index:
            items = sorted(set(ar))
            return np.asarray(items)
        else:
            ar = np.asarray(ar).flatten()

    if ar.size == 0:
        if return_inverse and return_index:
            return ar, np.empty(0, np.bool), np.empty(0, np.bool)
        elif return_inverse or return_index:
            return ar, np.empty(0, np.bool)
        else:
            return ar

    if return_inverse or return_index:
        perm = ar.argsort()
        aux = ar[perm]
        flag = np.concatenate(([True], aux[1:] != aux[:-1]))
        if return_inverse:
            iflag = np.cumsum(flag) - 1
            iperm = perm.argsort()
            if return_index:
                return aux[flag], perm[flag], iflag[iperm]
            else:
                return aux[flag], iflag[iperm]
        else:
            return aux[flag], perm[flag]

    else:
        ar.sort()
        flag = np.concatenate(([True], ar[1:] != ar[:-1]))
        return ar[flag]

np_version = []
for x in np.__version__.split('.'):
    try:
        np_version.append(int(x))
    except ValueError:
        # x may be of the form dev-1ea1592
        np_version.append(x)

if np_version[:2] < (1, 5):
    unique = _unique
else:
    unique = np.unique


def _bincount(X, weights=None, minlength=None):
    """Replacing np.bincount in numpy < 1.6 to provide minlength."""
    result = np.bincount(X, weights)
    if len(result) >= minlength:
        return result
    out = np.zeros(minlength, np.int)
    out[:len(result)] = result
    return out

if np_version[:2] < (1, 6):
    bincount = _bincount
else:
    bincount = np.bincount


def _copysign(x1, x2):
    """Slow replacement for np.copysign, which was introduced in numpy 1.4"""
    return np.abs(x1) * np.sign(x2)

if not hasattr(np, 'copysign'):
    copysign = _copysign
else:
    copysign = np.copysign


def _in1d(ar1, ar2, assume_unique=False):
    """Replacement for in1d that is provided for numpy >= 1.4"""
    if not assume_unique:
        ar1, rev_idx = unique(ar1, return_inverse=True)
        ar2 = np.unique(ar2)
    ar = np.concatenate((ar1, ar2))
    # We need this to be a stable sort, so always use 'mergesort'
    # here. The values from the first array should always come before
    # the values from the second array.
    order = ar.argsort(kind='mergesort')
    sar = ar[order]
    equal_adj = (sar[1:] == sar[:-1])
    flag = np.concatenate((equal_adj, [False]))
    indx = order.argsort(kind='mergesort')[:len(ar1)]

    if assume_unique:
        return flag[indx]
    else:
        return flag[indx][rev_idx]

if not hasattr(np, 'in1d'):
    in1d = _in1d
else:
    in1d = np.in1d


def _tril_indices(n, k=0):
    """Replacement for tril_indices that is provided for numpy >= 1.4"""
    mask = np.greater_equal(np.subtract.outer(np.arange(n), np.arange(n)), -k)
    indices = np.where(mask)

    return indices

if not hasattr(np, 'tril_indices'):
    tril_indices = _tril_indices
else:
    tril_indices = np.tril_indices


def _unravel_index(indices, dims):
    """Add support for multiple indices in unravel_index that is provided
    for numpy >= 1.4"""
    indices_arr = np.asarray(indices)
    if indices_arr.size == 1:
        return np.unravel_index(indices, dims)
    else:
        if indices_arr.ndim != 1:
            raise ValueError('indices should be one dimensional')

        ndims = len(dims)
        unraveled_coords = np.empty((indices_arr.size, ndims), dtype=np.int)
        for coord, idx in zip(unraveled_coords, indices_arr):
            coord[:] = np.unravel_index(idx, dims)
        return tuple(unraveled_coords.T)


if np_version[:2] < (1, 4):
    unravel_index = _unravel_index
else:
    unravel_index = np.unravel_index


def qr_economic(A, **kwargs):
    """Compat function for the QR-decomposition in economic mode

    Scipy 0.9 changed the keyword econ=True to mode='economic'
    """
    import scipy.linalg
    # trick: triangular solve has introduced in 0.9
    if hasattr(scipy.linalg, 'solve_triangular'):
        return scipy.linalg.qr(A, mode='economic', **kwargs)
    else:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return scipy.linalg.qr(A, econ=True, **kwargs)


def savemat(file_name, mdict, oned_as="column", **kwargs):
    """MATLAB-format output routine that is compatible with SciPy 0.7's.

    0.7.2 (or .1?) added the oned_as keyword arg with 'column' as the default
    value. It issues a warning if this is not provided, stating that "This will
    change to 'row' in future versions."
    """
    import scipy.io
    try:
        return scipy.io.savemat(file_name, mdict, oned_as=oned_as, **kwargs)
    except TypeError:
        return scipy.io.savemat(file_name, mdict, **kwargs)

if hasattr(np, 'count_nonzero'):
    from numpy import count_nonzero
else:
    def count_nonzero(X):
        return len(np.flatnonzero(X))

# little dance to see if np.copy has an 'order' keyword argument
if 'order' in inspect.getargspec(np.copy)[0]:
    def safe_copy(X):
        # Copy, but keep the order
        return np.copy(X, order='K')
else:
    # Before an 'order' argument was introduced, numpy wouldn't muck with
    # the ordering
    safe_copy = np.copy


# imported from scipy git master on 2012/12/12
from scipy.signal._arraytools import axis_slice, axis_reverse, odd_ext, \
                                     even_ext, const_ext
from scipy.signal import lfilter_zi, lfilter

def _filtfilt(b, a, x, axis=-1, padtype='odd', padlen=None):
    """A forward-backward filter.

    This function applies a linear filter twice, once forward
    and once backwards.  The combined filter has linear phase.

    Before applying the filter, the function can pad the data along the
    given axis in one of three ways: odd, even or constant.  The odd
    and even extensions have the corresponding symmetry about the end point
    of the data.  The constant extension extends the data with the values
    at end points.  On both the forward and backwards passes, the
    initial condition of the filter is found by using `lfilter_zi` and
    scaling it by the end point of the extended data.

    Parameters
    ----------
    b : array_like, 1-D
        The numerator coefficient vector of the filter.
    a : array_like, 1-D
        The denominator coefficient vector of the filter.  If a[0]
        is not 1, then both a and b are normalized by a[0].
    x : array_like
        The array of data to be filtered.
    axis : int, optional
        The axis of `x` to which the filter is applied.
        Default is -1.
    padtype : str or None, optional
        Must be 'odd', 'even', 'constant', or None.  This determines the
        type of extension to use for the padded signal to which the filter
        is applied.  If `padtype` is None, no padding is used.  The default
        is 'odd'.
    padlen : int or None, optional
        The number of elements by which to extend `x` at both ends of
        `axis` before applying the filter. This value must be less than
        `x.shape[axis]-1`.  `padlen=0` implies no padding.
        The default value is 3*max(len(a),len(b)).

    Returns
    -------
    y : ndarray
        The filtered output, an array of type numpy.float64 with the same
        shape as `x`.

    See Also
    --------
    lfilter_zi, lfilter

    Examples
    --------
    First we create a one second signal that is the sum of two pure sine
    waves, with frequencies 5 Hz and 250 Hz, sampled at 2000 Hz.

    >>> t = np.linspace(0, 1.0, 2001)
    >>> xlow = np.sin(2 * np.pi * 5 * t)
    >>> xhigh = np.sin(2 * np.pi * 250 * t)
    >>> x = xlow + xhigh

    Now create a lowpass Butterworth filter with a cutoff of 0.125 times
    the Nyquist rate, or 125 Hz, and apply it to x with filtfilt.  The
    result should be approximately xlow, with no phase shift.

    >>> from scipy import signal
    >>> b, a = signal.butter(8, 0.125)
    >>> y = signal.filtfilt(b, a, x, padlen=150)
    >>> np.abs(y - xlow).max()
    9.1086182074789912e-06

    We get a fairly clean result for this artificial example because
    the odd extension is exact, and with the moderately long padding,
    the filter's transients have dissipated by the time the actual data
    is reached.  In general, transient effects at the edges are
    unavoidable.
    """

    if padtype not in ['even', 'odd', 'constant', None]:
        raise ValueError(("Unknown value '%s' given to padtype.  padtype must "
                         "be 'even', 'odd', 'constant', or None.") %
                            padtype)

    b = np.asarray(b)
    a = np.asarray(a)
    x = np.asarray(x)

    ntaps = max(len(a), len(b))

    if padtype is None:
        padlen = 0

    if padlen is None:
        # Original padding; preserved for backwards compatibility.
        edge = ntaps * 3
    else:
        edge = padlen

    # x's 'axis' dimension must be bigger than edge.
    if x.shape[axis] <= edge:
        raise ValueError("The length of the input vector x must be at least "
                         "padlen, which is %d." % edge)

    if padtype is not None and edge > 0:
        # Make an extension of length `edge` at each
        # end of the input array.
        if padtype == 'even':
            ext = even_ext(x, edge, axis=axis)
        elif padtype == 'odd':
            ext = odd_ext(x, edge, axis=axis)
        else:
            ext = const_ext(x, edge, axis=axis)
    else:
        ext = x

    # Get the steady state of the filter's step response.
    zi = lfilter_zi(b, a)

    # Reshape zi and create x0 so that zi*x0 broadcasts
    # to the correct value for the 'zi' keyword argument
    # to lfilter.
    zi_shape = [1] * x.ndim
    zi_shape[axis] = zi.size
    zi = np.reshape(zi, zi_shape)
    x0 = axis_slice(ext, stop=1, axis=axis)

    # Forward filter.
    (y, zf) = lfilter(b, a, ext, axis=axis, zi=zi * x0)

    # Backward filter.
    # Create y0 so zi*y0 broadcasts appropriately.
    y0 = axis_slice(y, start=-1, axis=axis)
    (y, zf) = lfilter(b, a, axis_reverse(y, axis=axis), axis=axis, zi=zi * y0)

    # Reverse y.
    y = axis_reverse(y, axis=axis)

    if edge > 0:
        # Slice the actual signal from the extended signal.
        y = axis_slice(y, start=edge, stop=-edge, axis=axis)

    return y

from scipy.signal import filtfilt
if 'padlen' not in inspect.getargspec(filtfilt)[0]:
    filtfilt = _filtfilt


###############################################################################
# Back porting firwin2 for older scipy

# Original version of firwin2 from scipy ticket #457, submitted by "tash".
#
# Rewritten by Warren Weckesser, 2010.


def _firwin2(numtaps, freq, gain, nfreqs=None, window='hamming', nyq=1.0):
    """FIR filter design using the window method.

    From the given frequencies `freq` and corresponding gains `gain`,
    this function constructs an FIR filter with linear phase and
    (approximately) the given frequency response.

    Parameters
    ----------
    numtaps : int
        The number of taps in the FIR filter.  `numtaps` must be less than
        `nfreqs`.  If the gain at the Nyquist rate, `gain[-1]`, is not 0,
        then `numtaps` must be odd.

    freq : array-like, 1D
        The frequency sampling points. Typically 0.0 to 1.0 with 1.0 being
        Nyquist.  The Nyquist frequency can be redefined with the argument
        `nyq`.

        The values in `freq` must be nondecreasing.  A value can be repeated
        once to implement a discontinuity.  The first value in `freq` must
        be 0, and the last value must be `nyq`.

    gain : array-like
        The filter gains at the frequency sampling points.

    nfreqs : int, optional
        The size of the interpolation mesh used to construct the filter.
        For most efficient behavior, this should be a power of 2 plus 1
        (e.g, 129, 257, etc).  The default is one more than the smallest
        power of 2 that is not less than `numtaps`.  `nfreqs` must be greater
        than `numtaps`.

    window : string or (string, float) or float, or None, optional
        Window function to use. Default is "hamming".  See
        `scipy.signal.get_window` for the complete list of possible values.
        If None, no window function is applied.

    nyq : float
        Nyquist frequency.  Each frequency in `freq` must be between 0 and
        `nyq` (inclusive).

    Returns
    -------
    taps : numpy 1D array of length `numtaps`
        The filter coefficients of the FIR filter.

    Examples
    --------
    A lowpass FIR filter with a response that is 1 on [0.0, 0.5], and
    that decreases linearly on [0.5, 1.0] from 1 to 0:

    >>> taps = firwin2(150, [0.0, 0.5, 1.0], [1.0, 1.0, 0.0])
    >>> print(taps[72:78])
    [-0.02286961 -0.06362756  0.57310236  0.57310236 -0.06362756 -0.02286961]

    See also
    --------
    scipy.signal.firwin

    Notes
    -----

    From the given set of frequencies and gains, the desired response is
    constructed in the frequency domain.  The inverse FFT is applied to the
    desired response to create the associated convolution kernel, and the
    first `numtaps` coefficients of this kernel, scaled by `window`, are
    returned.

    The FIR filter will have linear phase.  The filter is Type I if `numtaps`
    is odd and Type II if `numtaps` is even.  Because Type II filters always
    have a zero at the Nyquist frequency, `numtaps` must be odd if `gain[-1]`
    is not zero.

    .. versionadded:: 0.9.0

    References
    ----------
    .. [1] Oppenheim, A. V. and Schafer, R. W., "Discrete-Time Signal
       Processing", Prentice-Hall, Englewood Cliffs, New Jersey (1989).
       (See, for example, Section 7.4.)

    .. [2] Smith, Steven W., "The Scientist and Engineer's Guide to Digital
       Signal Processing", Ch. 17. http://www.dspguide.com/ch17/1.htm

    """

    if len(freq) != len(gain):
        raise ValueError('freq and gain must be of same length.')

    if nfreqs is not None and numtaps >= nfreqs:
        raise ValueError('ntaps must be less than nfreqs, but firwin2 was '
                    'called with ntaps=%d and nfreqs=%s' % (numtaps, nfreqs))

    if freq[0] != 0 or freq[-1] != nyq:
        raise ValueError('freq must start with 0 and end with `nyq`.')
    d = np.diff(freq)
    if (d < 0).any():
        raise ValueError('The values in freq must be nondecreasing.')
    d2 = d[:-1] + d[1:]
    if (d2 == 0).any():
        raise ValueError('A value in freq must not occur more than twice.')

    if numtaps % 2 == 0 and gain[-1] != 0.0:
        raise ValueError("A filter with an even number of coefficients must "
                            "have zero gain at the Nyquist rate.")

    if nfreqs is None:
        nfreqs = 1 + 2 ** int(ceil(log(numtaps, 2)))

    # Tweak any repeated values in freq so that interp works.
    eps = np.finfo(float).eps
    for k in range(len(freq)):
        if k < len(freq) - 1 and freq[k] == freq[k + 1]:
            freq[k] = freq[k] - eps
            freq[k + 1] = freq[k + 1] + eps

    # Linearly interpolate the desired response on a uniform mesh `x`.
    x = np.linspace(0.0, nyq, nfreqs)
    fx = np.interp(x, freq, gain)

    # Adjust the phases of the coefficients so that the first `ntaps` of the
    # inverse FFT are the desired filter coefficients.
    shift = np.exp(-(numtaps - 1) / 2. * 1.j * np.pi * x / nyq)
    fx2 = fx * shift

    # Use irfft to compute the inverse FFT.
    out_full = irfft(fx2)

    if window is not None:
        # Create the window to apply to the filter coefficients.
        from scipy.signal.signaltools import get_window
        wind = get_window(window, numtaps, fftbins=False)
    else:
        wind = 1

    # Keep only the first `numtaps` coefficients in `out`, and multiply by
    # the window.
    out = out_full[:numtaps] * wind

    return out

if hasattr(scipy.signal, 'firwin2'):
    from scipy.signal import firwin2
else:
    firwin2 = _firwin2
