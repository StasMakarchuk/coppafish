import numpy as np
import scipy.signal
from scipy.ndimage.morphology import grey_dilation
from scipy.ndimage import convolve, correlate
import numbers
import iss.utils.errors
import cv2
from math import floor


class Strel:
    @staticmethod
    def periodic_line(p, v):
        """
        creates a flat structuring element
        containing 2*p+1 members.  v is a two-element vector containing
        integer-valued row and column offsets.  One structuring element member
        is located at the origin.  The other members are located at 1*v, -1*v,
        2*v, -2*v, ..., p*v, -p*v.
        copy of MATLAB strel('periodicline')
        """
        pp = np.repeat(np.arange(-p, p + 1).reshape(-1, 1), 2, axis=1)
        rc = pp * v
        r = rc[:, 0]
        c = rc[:, 1]
        M = 2 * np.abs(r).max() + 1
        N = 2 * np.abs(c).max() + 1
        nhood = np.zeros((M, N), dtype=bool)
        # idx = np.ravel_multi_index([r + np.abs(r).max(), c + np.abs(c).max()], (M, N))
        nhood[r + np.abs(r).max(), c + np.abs(c).max()] = True
        return nhood.astype(np.uint8)

    @classmethod
    def disk(cls, r, n=4):
        """
        creates a flat disk-shaped structuring element
        with the specified radius, r.  r must be a nonnegative integer.  n must
        be 0, 4, 6, or 8.  When n is greater than 0, the disk-shaped structuring
        element is approximated by a sequence of n (or sometimes n+2)
        periodic-line structuring elements.  When n is 0, no approximation is
        used, and the structuring element members comprise all pixels whose
        centers are no greater than r away from the origin.  n can be omitted,
        in which case its default value is 4.  Note: Morphological operations
        using disk approximations (n>0) run much faster than when n=0.  Also,
        the structuring elements resulting from choosing n>0 are suitable for
        computing granulometries, which is not the case for n=0.  Sometimes it
        is necessary for STREL to use two extra line structuring elements in the
        approximation, in which case the number of decomposed structuring
        elements used is n+2.
        copy of MATLAB strel('disk')
        """
        if r < 3:
            # Radius is too small to use decomposition, so force n=0.
            n = 0
        if n == 0:
            xx, yy = np.meshgrid(np.arange(-r, r + 1), np.arange(-r, r + 1))
            nhood = xx ** 2 + yy ** 2 <= r ** 2
        else:
            """
            Reference for radial decomposition of disks:  Rolf Adams, "Radial
            Decomposition of Discs and Spheres," CVGIP:  Graphical Models and
            Image Processing, vol. 55, no. 5, September 1993, pp. 325-332.
            
            The specific decomposition technique used here is radial
            decomposition using periodic lines.  The reference is:  Ronald
            Jones and Pierre Soille, "Periodic lines: Definition, cascades, and
            application to granulometries," Pattern Recognition Letters,
            vol. 17, 1996, pp. 1057-1063.
            
            Determine the set of "basis" vectors to be used for the
            decomposition.  The rows of v will be used as offset vectors for
            periodic line strels.
            """
            if n == 4:
                v = np.array([[1, 0], [1, 1], [0, 1], [-1, 1]])
            elif n == 6:
                v = np.array([[1, 0], [1, 2], [2, 1], [0, 1], [-1, 2], [-2, 1]])
            elif n == 8:
                v = np.array([[1, 0], [2, 1], [1, 1], [1, 2], [0, 1], [-1, 2], [-1, 1], [-2, 1]])
            else:
                raise ValueError(f'Value of n provided ({n}) is not 0, 4, 6 or 8.')
            # Determine k, which is the desired radial extent of the periodic
            # line strels.  For the origin of this formula, see the second
            # paragraph on page 328 of the Rolf Adams paper.
            theta = np.pi / (2 * n)
            k = 2 * r / (1 / np.tan(theta) + 1 / np.sin(theta))

            # For each periodic line strel, determine the repetition parameter,
            # rp.  The use of floor() in the computation means that the resulting
            # strel will be a little small, but we will compensate for this
            # below.
            nhood = np.ones((2 * r - 1, 2 * r - 1), np.uint8) * -np.inf
            nhood[int((nhood.shape[0] - 1) / 2), int((nhood.shape[0] - 1) / 2)] = 1
            for q in range(n):
                rp = int(np.floor(k / np.linalg.norm(v[q, :])))
                decomposition = cls.periodic_line(rp, v[q, :])
                nhood = dilate(nhood, decomposition)
            nhood = nhood > 0

            # Now we are going to add additional vertical and horizontal line
            # strels to compensate for the fact that the strel resulting from the
            # above decomposition tends to be smaller than the desired size.
            extra_strel_size = int(sum(np.sum(nhood, axis=1) == 0) + 1)
            if extra_strel_size > 0:
                # Update the computed neighborhood to reflect the additional strels in
                # the decomposition.
                nhood = cv2.dilate(nhood.astype(np.uint8), np.ones((1, extra_strel_size), dtype=np.uint8))
                nhood = cv2.dilate(nhood, np.ones((extra_strel_size, 1), dtype=np.uint8))
                nhood = nhood > 0
        return nhood.astype(int)

    @staticmethod
    def disk_3d(r_xy, r_z):
        """
        gets structuring element used to find spots when dilated with 3d image.

        :param r_xy: integer
        :param r_z: integer
        :return: numpy integer array [2*r_xy+1, 2*r_xy+1, 2*r_z+1]. Each element either 0 or 1.
        """
        y, x, z = np.meshgrid(np.arange(-r_xy, r_xy + 1), np.arange(-r_xy, r_xy + 1), np.arange(-r_z, r_z + 1))
        se = x ** 2 + y ** 2 + z ** 2 <= r_xy ** 2
        return se.astype(int)

    @staticmethod
    def annulus(r0, r_xy, r_z=None):
        """
        gets structuring element used to assess if spot isolated

        :param r0: float
            inner radius within which values are all zero.
        :param r_xy: float
            outer radius in xy direction.
            can be float not integer because all values with radius < r_xy1 and > r0 will be set to 1.
        :param r_z: float, optional
            outer radius in z direction. (size in z-pixels not normalised to xy pixel size). 
            default: None meaning 2d annulus.
        :return: numpy integer array [2*floor(r_xy1)+1, 2*floor(r_xy1)+1, 2*floor(r_z1)+1]. Each element either 0 or 1.
        """
        r_xy1_int = floor(r_xy)
        if r_z is None:
            y, x = np.meshgrid(np.arange(-r_xy1_int, r_xy1_int + 1), np.arange(-r_xy1_int, r_xy1_int + 1))
            m = x ** 2 + y ** 2
        else:
            r_z1_int = floor(r_z)
            y, x, z = np.meshgrid(np.arange(-r_xy1_int, r_xy1_int + 1), np.arange(-r_xy1_int, r_xy1_int + 1),
                                  np.arange(-r_z1_int, r_z1_int + 1))
            m = x ** 2 + y ** 2 + z ** 2
        # only use upper radius in xy direction as z direction has different pixel size.
        annulus = r_xy ** 2 >= m
        annulus = np.logical_and(annulus, m > r0 ** 2)
        return annulus.astype(int)


def ftrans2(b, t=None):
    """
    Produces a 2D convolve_2d that corresponds to the 1D convolve_2d b, using the transform t
    Copied from MATLAB ftrans2: https://www.mathworks.com/help/images/ref/ftrans2.html

    :param b: float numpy array [Q,]
    :param t: float numpy array [M, N], optional.
        default: McClellan transform
    :return: float numpy array [(M-1)*(Q-1)/2+1, (N-1)*(Q-1)/2+1]
    """
    if t is None:
        # McClellan transformation
        t = np.array([[1, 2, 1], [2, -4, 2], [1, 2, 1]]) / 8

    # Convert the 1-D convolve_2d b to SUM_n a(n) cos(wn) form
    n = int(round((len(b) - 1) / 2))
    b = b.reshape(-1, 1)
    b = np.rot90(np.fft.fftshift(np.rot90(b)))
    a = np.concatenate((b[:1], 2 * b[1:n + 1]))

    inset = np.floor((np.array(t.shape) - 1) / 2).astype(int)

    # Use Chebyshev polynomials to compute h
    p0 = 1
    p1 = t
    h = a[1] * p1
    rows = inset[0]
    cols = inset[1]
    h[rows, cols] += a[0] * p0
    for i in range(2, n + 1):
        p2 = 2 * scipy.signal.convolve2d(t, p1)
        rows = rows + inset[0]
        cols = cols + inset[1]
        p2[rows, cols] -= p0
        rows = inset[0] + np.arange(p1.shape[0])
        cols = (inset[1] + np.arange(p1.shape[1])).reshape(-1, 1)
        hh = h.copy()
        h = a[i] * p2
        h[rows, cols] += hh
        p0 = p1.copy()
        p1 = p2.copy()
    h = np.rot90(h)
    return h


def hanning_diff(r1, r2):
    """
    gets difference of two hanning window convolve_2d
    (central positive, outer negative) with sum of 0.

    :param r1: integer
        radius in pixels of central positive hanning convolve_2d
    :param r2: integer, must be greater than r1
        radius in pixels of outer negative hanning convolve_2d
    :return: float numpy array [2*r2 + 1, 2*r2 + 1]
    """
    iss.utils.errors.out_of_bounds('r1', r1, 0, r2)
    iss.utils.errors.out_of_bounds('r2', r2, r1, np.inf)
    h_outer = np.hanning(2 * r2 + 3)[1:-1]  # ignore zero values at first and last index
    h_outer = -h_outer / h_outer.sum()
    h_inner = np.hanning(2 * r1 + 3)[1:-1]
    h_inner = h_inner / h_inner.sum()
    h = h_outer.copy()
    h[r2 - r1:r2 + r1 + 1] += h_inner
    h = ftrans2(h)
    return h


def convolve_2d(image, kernel):
    """
    convolves image with kernel, padding by replicating border pixels
    np.flip is to give same as convn with replicate padding in MATLAB

    :param image: numpy array [image_sz1 x image_sz2]
    :param kernel: numpy float array
    :return: numpy float array [image_sz1 x image_sz2]
    """
    return cv2.filter2D(image.astype(float), -1, np.flip(kernel), borderType=cv2.BORDER_REPLICATE)


def ensure_odd_kernel(kernel, pad_location='start'):
    """
    This ensures all dimensions of kernel are odd by padding even dimensions with zeros.
    Replicates MATLAB way of dealing with even kernels.
    e.g. if pad_location is 'start': [[5,4];[3,1]] --> [[0,0,0],[0,5,4],[0,3,1]]

    :param kernel: numpy float array
        Multidimensional filter
    :param pad_location: string either 'start' or 'end'
        where to put zeros.
    :return: numpy float array
    """
    even_dims = (np.mod(kernel.shape, 2) == 0).astype(int)
    if max(even_dims) == 1:
        if pad_location == 'start':
            pad_dims = [tuple(np.array([1, 0]) * val) for val in even_dims]
        elif pad_location == 'end':
            pad_dims = [tuple(np.array([0, 1]) * val) for val in even_dims]
        else:
            raise ValueError(f"pad_location has to be either 'start' or 'end' but value given was {pad_location}.")
        return np.pad(kernel, pad_dims, mode='constant')
    else:
        return kernel


def top_hat(image, kernel):
    """
    does tophat filtering of image with kernel

    :param image: numpy float array [image_sz1 x image_sz2]
    :param kernel: numpy integer array containing only zeros or ones.
    :return: numpy float array [image_sz1 x image_sz2]
    """
    if np.max(np.mod(kernel.shape, 2) == 0):
        # With even kernel, gives different results to MATLAB
        raise ValueError(f'kernel dimensions are {kernel.shape}. Require all dimensions to be odd.')
    # kernel = ensure_odd_kernel(kernel)  # doesn't work for tophat at start or end.
    return cv2.morphologyEx(image, cv2.MORPH_TOPHAT, kernel)


def dilate(image, kernel):
    """
    dilates image with kernel, using zero padding.

    :param image: numpy float array [image_sz1 x image_sz2]
    :param kernel: numpy integer array containing only zeros or ones.
    :return: numpy float array [image_sz1 x image_sz2]
    """
    kernel = ensure_odd_kernel(kernel)
    # mode refers to the padding. We pad with zeros to keep results the same as MATLAB
    return grey_dilation(image, footprint=kernel, mode='constant')
    # return morphology.dilation(image, kernel)


def imfilter(image, kernel, padding=0, corr_or_conv='corr'):
    """
    copy of MATLAB imfilter function with 'output_size' equal to 'same'.

    :param image: numpy float array [image_sz1 x image_sz2]
        Image to be filtered
    :param kernel: numpy float array
        Multidimensional filter
    :param padding:
        numeric scalar: Input array values outside the bounds of the array are assigned the value X.
                        When no padding option is specified, the default is 0.
        ‘reflect’: 	    Input array values outside the bounds of the array are computed by
                        mirror-reflecting the array across the array border.
        ‘nearest’:      Input array values outside the bounds of the array are assumed to equal
                        the nearest array border value.
        'wrap':         Input array values outside the bounds of the array are computed by implicitly
                        assuming the input array is periodic.
    :param corr_or_conv:
        'corr':         imfilter performs multidimensional filtering using correlation.
                        This is the default when no option specified.
        'conv':         imfilter performs multidimensional filtering using convolution.
    :return: numpy float array [image_sz1 x image_sz2]
    """
    if isinstance(padding, numbers.Number):
        pad_value = padding
        padding = 'constant'
    else:
        pad_value = 0.0  # doesn't do anything for non-constant padding
    if corr_or_conv == 'corr':
        kernel = ensure_odd_kernel(kernel, 'start')
        return correlate(image, kernel, mode=padding, cval=pad_value)
    elif corr_or_conv == 'conv':
        kernel = ensure_odd_kernel(kernel, 'end')
        return convolve(image, kernel, mode=padding, cval=pad_value)
    else:
        raise ValueError(f"corr_or_conv should be either 'corr' or 'conv' but given value is {corr_or_conv}")
