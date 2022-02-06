from .. import utils, extract, setup
import numpy as np
import os
from tqdm import tqdm


def extract_and_filter(config, nbp_file, nbp_basic):
    """

    :param config:
    :param nbp_file:
    :param nbp_basic:
    :return:
    """
    # initialise notebook pages
    if not nbp_basic.is_3d:
        config['deconvolve'] = False  # only deconvolve if 3d pipeline
    nbp = setup.NotebookPage("extract")
    nbp_debug = setup.NotebookPage("extract_debug")
    # initialise output of this part of pipeline as 'vars' key
    nbp.auto_thresh = np.zeros((nbp_basic.n_tiles, nbp_basic.n_rounds + nbp_basic.n_extra_rounds,
                                nbp_basic.n_channels))
    nbp.hist_values = np.arange(-nbp_basic.tile_pixel_value_shift, np.iinfo(np.uint16).max -
                                   nbp_basic.tile_pixel_value_shift + 2, 1)
    nbp.hist_counts = np.zeros((len(nbp.hist_values), nbp_basic.n_rounds + nbp_basic.n_extra_rounds,
                                   nbp_basic.n_channels), dtype=int)
    hist_bin_edges = np.concatenate(
        (nbp.hist_values - 0.5, nbp.hist_values[-1:] + 0.5))
    # initialise debugging info as 'debug' page
    nbp_debug.n_clip_pixels = np.zeros_like(nbp.auto_thresh, dtype=int)
    nbp_debug.clip_extract_scale = np.zeros_like(nbp.auto_thresh)

    # update config params in notebook. All optional parameters in config are added to debug page
    if config['r1'] is None:
        config['r1'] = extract.get_pixel_length(config['r1_auto_microns'], nbp_basic.pixel_size_xy)
    if config['r2'] is None:
        config['r2'] = config['r1'] * 2
    if config['r_dapi'] is None:
        config['r_dapi'] = extract.get_pixel_length(config['r_dapi_auto_microns'], nbp_basic.pixel_size_xy)
    nbp_debug.r1 = config['r1']
    nbp_debug.r2 = config['r1']
    nbp_debug.r_dapi = config['r1']

    filter_kernel = utils.morphology.hanning_diff(nbp_debug.r1, nbp_debug.r2)
    filter_kernel_dapi = utils.strel.disk(nbp_debug.r_dapi)

    if config['deconvolve']:
        # TODO: add smooth as well as this seems to work well with quadcam
        if not os.path.isfile(nbp_file.psf):
            if nbp_basic.ref_round == nbp_basic.anchor_round:
                im_file = os.path.join(nbp_file.input_dir, nbp_file.anchor + nbp_file.raw_extension)
            else:
                im_file = os.path.join(nbp_file.input_dir,
                                       nbp_file.round[nbp_basic.ref_round] + nbp_file.raw_extension)

            spot_images, config['psf_intensity_thresh'], psf_tiles_used = \
                extract.get_psf_spots(im_file, nbp_basic.tilepos_yx, nbp_basic.tilepos_yx_nd2,
                                      nbp_basic.use_tiles, nbp_basic.ref_channel, nbp_basic.use_z,
                                      config['psf_detect_radius_xy'], config['psf_detect_radius_z'],
                                      config['psf_min_spots'], config['psf_intensity_thresh'],
                                      config['auto_thresh_multiplier'], config['psf_isolation_dist'],
                                      config['psf_shape'])
            psf = extract.get_psf(spot_images, config['psf_annulus_width'])
            utils.tiff.save(psf*np.iinfo(np.uint16).max, nbp_file.psf)  # scale psf to fill uint16 range
        else:
            psf = utils.tiff.load(nbp_file.psf).astype(float)
            psf_tiles_used = None
        # normalise psf so min is 0 and max is 1.
        psf = psf - psf.min()
        psf = psf / psf.max()
        pad_im_shape = np.array([nbp_basic.tile_sz, nbp_basic.tile_sz, nbp_basic.nz]) + \
                       np.array(config['wiener_pad_shape']) * 2
        wiener_filter = extract.get_wiener_filter(psf, pad_im_shape, config['wiener_constant'])
        nbp_debug.psf = psf
        nbp_debug.psf_intensity_thresh = config['psf_intensity_thresh']
        nbp_debug.psf_tiles_used = psf_tiles_used

    if config['scale'] is None:
        # ensure scale_norm value is reasonable so max pixel value in tiff file is significant factor of max of uint16
        scale_norm_min = (np.iinfo('uint16').max - nbp_basic.tile_pixel_value_shift) / 5
        scale_norm_max = np.iinfo('uint16').max - nbp_basic.tile_pixel_value_shift
        if not scale_norm_min <= config['scale_norm'] <= scale_norm_max:
            raise utils.errors.OutOfBoundsError("scale_norm", config['scale_norm'], scale_norm_min, scale_norm_max)
        im_file = os.path.join(nbp_file.input_dir, nbp_file.round[0] + nbp_file.raw_extension)
        nbp_debug.scale_tile, nbp_debug.scale_channel, nbp_debug.scale_z, config['scale'] = \
            extract.get_scale(im_file, nbp_basic.tilepos_yx, nbp_basic.tilepos_yx_nd2,
                              nbp_basic.use_tiles, nbp_basic.use_channels, nbp_basic.use_z,
                              config['scale_norm'], filter_kernel)
    nbp_debug.scale = config['scale']

    '''get rounds to iterate over'''
    use_channels_anchor = [c for c in [nbp_basic.dapi_channel, nbp_basic.anchor_channel] if c is not None]
    use_channels_anchor.sort()
    if nbp_basic.anchor_round is not None:
        # always have anchor as first round after imaging rounds
        round_files = nbp_file.round + [nbp_file.anchor]
        use_rounds = nbp_basic.use_rounds + [nbp_basic.n_rounds]
        n_images = (len(use_rounds) - 1) * len(nbp_basic.use_tiles) * len(nbp_basic.use_channels) + \
                        len(nbp_basic.use_tiles) * len(use_channels_anchor)
    else:
        round_files = nbp_file.round
        use_rounds = nbp_basic.use_rounds
        n_images = len(use_rounds) * len(nbp_basic.use_tiles) * len(nbp_basic.use_channels)

    with tqdm(total=n_images) as pbar:
        for r in use_rounds:
            # set scale and channels to use
            im_file = os.path.join(nbp_file.input_dir, round_files[r] + nbp_file.raw_extension)
            extract.wait_for_data(im_file, config['wait_time'])
            images = utils.nd2.load(im_file)
            if r == nbp_basic.anchor_round:
                if config['scale_anchor'] is None:
                    nbp_debug.scale_anchor_tile, _, nbp_debug.scale_anchor_z, config['scale_anchor'] = \
                        extract.get_scale(im_file, nbp_basic.tilepos_yx, nbp_basic.tilepos_yx_nd2,
                                          nbp_basic.use_tiles, [nbp_basic.anchor_channel], nbp_basic.use_z,
                                          config['scale_norm'], filter_kernel)
                nbp_debug.scale_anchor = config['scale_anchor']
                scale = nbp_debug.scale_anchor
                use_channels = use_channels_anchor
            else:
                scale = nbp_debug.scale
                use_channels = nbp_basic.use_channels

            # convolve_2d each image
            for t in nbp_basic.use_tiles:
                if not nbp_basic.is_3d:
                    # for 2d all channels in same file
                    file_exists = os.path.isfile(nbp_file.tile[t][r])
                for c in range(nbp_basic.n_channels):
                    if c in use_channels:
                        if nbp_basic.is_3d:
                            file_exists = os.path.isfile(nbp_file.tile[t][r][c])
                        pbar.set_postfix({'round': r, 'tile': t, 'channel': c, 'exists': str(file_exists)})
                        if file_exists:
                            nbp, nbp_debug = extract.update_log_extract(nbp_file, nbp_basic, nbp, nbp_debug,
                                                                        config['auto_thresh_multiplier'],
                                                                        hist_bin_edges, t, r, c)
                        else:
                            im = utils.nd2.get_image(images, extract.get_nd2_tile_ind(t, nbp_basic.tilepos_yx_nd2,
                                                                                      nbp_basic.tilepos_yx),
                                                     c, nbp_basic.use_z)
                            if not nbp_basic.is_3d:
                                im = extract.focus_stack(im)
                            else:
                                im = im.astype(int)
                            im, bad_columns = extract.strip_hack(im)  # find faulty columns
                            if config['deconvolve']:
                                im = extract.wiener_deconvolve(im, config['wiener_pad_shape'], wiener_filter)
                            if r == nbp_basic.anchor_round and c == nbp_basic.dapi_channel:
                                im = utils.morphology.top_hat(im, filter_kernel_dapi)
                                im[:, bad_columns] = 0
                            else:
                                im = utils.morphology.convolve_2d(im, filter_kernel) * scale
                                im[:, bad_columns] = 0
                                im = np.round(im).astype(int)
                                # TODO: make below quicker by getting from one z-plane
                                nbp, nbp_debug = extract.update_log_extract(nbp_file, nbp_basic, nbp, nbp_debug,
                                                                            config['auto_thresh_multiplier'],
                                                                            hist_bin_edges, t, r, c, im, bad_columns)
                            utils.tiff.save_tile(nbp_file, nbp_basic, nbp_debug, im, t, r, c)
                        pbar.update(1)
                    elif not nbp_basic.is_3d and not file_exists:
                        # if not including channel, just set to all zeros
                        # only in 2D as all channels in same file - helps when loading in tiffs
                        im = np.zeros((nbp_basic.tile_sz, nbp_basic.tile_sz), dtype=np.uint16)
                        utils.tiff.save_tile(nbp_file, nbp_basic, nbp_debug, im, t, r, c)
    pbar.close()
    return nbp, nbp_debug
