# Extract and Filter

The extract and filter step of the pipeline loads in the raw images, filters them and saves
the resultant filtered images for each tile/round/channel combination as [npy files](../config_setup.md#tile_dir).

It also adds the [`extract`](../notebook_comments.md#extract) and 
[`extract_debug`](../notebook_comments.md#extract_debug) *NotebookPages* to the *Notebook*.

## Raw data

The raw data can be viewed using [`view_raw`](../code/plot/raw.md#iss.plot.raw.view_raw). It can either be called
for an experiment which already has a *Notebook* or for one which no code has been run yet but the `config_file` 
has been made:

=== "With *Notebook*"

    ``` python
    from iss import Notebook
    from iss.plot import view_raw
    nb_file = '/Users/user/iss/experiment/notebook.npz'
    nb = Notebook(nb_file)
    tiles = [0, 1]      # tiles to view
    rounds = [3, 5]     # rounds to view
    channels = [1, 6]   # channels to view
    view_raw(nb, tiles, rounds, channels)
    ```

=== "Without *Notebook*"

    ``` python
    from iss.plot import view_raw
    ini_file = '/Users/user/iss/experiment/settings.ini'
    tiles = [0, 1]      # tiles to view
    rounds = [3, 5]     # rounds to view
    channels = [1, 6]   # channels to view
    view_raw(None, tiles, rounds, channels, config_file=ini_file)
    ```

This will open a napari viewer with up to 4 scrollbars to change tile, round, channel and z-plane.
When any of these scrollbars are used, the status in the bottom left corner will indicate the current tile, round, 
channel and z-plane being shown (e.g. below, the round at index 0 is 3 and the channel at index 1 is 6).

![raw](../images/pipeline/extract/raw.png){width="800"}


## Filtering
Once the raw images are loaded in, they are 
[convolved](../code/utils/morphology.md#iss.utils.morphology.base.convolve_2d) with a *2D* 
[difference of hanning kernel](../code/utils/morphology.md#iss.utils.morphology.base.hanning_diff).

??? note "Difference with *2D* pipeline"
    
    If `config['basic_info']['is_3d'] == False`, before the convolution with the difference of hanning kernel,
    the *3D* raw data will be [focus stacked](../code/extract/fstack.md#iss.extract.fstack.focus_stack) so that 
    it becomes *2D*.

### Difference of hanning kernel
The [difference of hanning kernel](../code/utils/morphology.md#iss.utils.morphology.base.hanning_diff) is made up
by adding together a positive hanning window (yellow below) of radius $r_1$ and an outer negative hanning window 
(cyan below) of radius of $r_2$ (typically twice $r_1$).
It is normalised such that the sum of the difference of hanning kernel is 0. An example for a *1D* version of the 
kernel with $r_1 = 3$ and $r_2 = 6$:

![hanning](../images/pipeline/extract/hanning.png){width="800"}

??? note "Conversion to *2D*"

    ![hanning](../images/pipeline/extract/hanning_2d.png){width="400", align=right}
    
    The *1D* kernel shown in purple above is converted to the *2D* kernel shown on the right via the 
    [`ftrans2`](../code/utils/morphology.md#iss.utils.morphology.base.ftrans2) function.

In the pipeline, the value of $r_1$ is set to [`config['extract']['r1']`](../config.md#extract) 
and $r_2$ is set to `config['extract']['r2']`.
If `config['extract']['r1']` is not specified, it is converted to units of pixels from the micron value
`config['extract']['r1_auto_microns']` (0.5$\mu$m typically gives $r_1=3$). If `config['extract']['r2']` is not 
specified, $r_2$ is set to twice $r_1$. 

In general, $r_1$ should be the typical radius of a spot in the raw image and $r_2$ should be twice this.

### Smoothing
After the convolution with the difference of hanning kernel, there is an option to smooth the image by applying 
a [correlation](../code/utils/morphology.md#iss.utils.morphology.filter.imfilter) with an averaging kernel.
This can be included by setting the [`config['extract']['r_smooth']`](../config_setup.md#extractr_smooth) parameter. 


### DAPI
For the `dapi_channel` of the `anchor_round`, convolution with the difference of hanning kernel is not appropriate 
as the features that need extracting do not look like spots. Instead, tophat filtering can be performed by 
setting [`config['extract']['r_dapi']`](../config_setup.md#extractr_dapi) and no smoothing is permitted.


## Viewer
The purpose of filtering the raw images is to make the spots appear much more prominently compared to the background 
i.e. it is to extract the spots. We can see this effect and how the various parameters affect things with 
[`view_filter`](../code/plot/extract.md#iss.plot.extract.view_filter). 
This can be called in a similar way to [`view_raw`](#raw-data):

=== "With *Notebook*"

    ``` python
    from iss import Notebook
    from iss.plot import view_filter
    nb_file = '/Users/user/iss/experiment/notebook.npz'
    nb = Notebook(nb_file)
    t = 1       # tile to view
    r = 3       # round to view
    c = 6       # channels to view
    view_raw(nb, t, r, c)
    ```

=== "Without *Notebook*"

    ``` python
    from iss.plot import view_filter
    ini_file = '/Users/user/iss/experiment/settings.ini'
    t = 1       # tile to view
    r = 3       # round to view
    c = 6       # channels to view
    view_raw(None, t, r, c, config_file=ini_file)
    ```

This will open a napari viewer with up to 2 scrollbars. One to change z-plane and another to change the filter method.
The filter method scrollbar can change between the raw image, the result of convolution with difference of hanning 
kernel and the result with smoothing in addition to this.

There are also up to 3 of the following sliders in the bottom left:

* *Difference of Hanning Radius*: This is the value of `config['extract']['r1']`. 
Whenever this is changed, `config['extract']['r2']` will be set to twice the new value.
* *Tophat kernel radius*: If `r == anchor_round` and `c == dapi_channel`, this slider will appear and refers to the 
value of `config['extract']['r_dapi']`.
* *Smooth Radius YX*: This is the value of `config['extract']['r_smooth'][0]` and `config['extract']['r_smooth'][1]`.
Both will be set to the same value.
* *Smooth Radius Z*: This is the value of `config['extract']['r_smooth'][2]`. When both this slider and 
the *Smooth Radius YX* slider are set to 1, no smoothing will be performed and the last two images in the filter method
scrollbar will be identical.

Whenever any of these are changed, the filtering will be redone using the new values of the parameters
and thus the last two images of the filter method scrollbar will be updated.
The time taken will be printed to the console.

The *1D* version of the current difference of hanning kernel can be seen at any time by pressing the *h* key.

### Effect of Filtering
The images below show the effect of filtering with `config['extract']['r1'] = 3`, `config['extract']['r2'] = 6`
and `config['extract']['r_smooth'] = 1, 1, 2`:

=== "Raw"
    ![image](../images/pipeline/extract/viewer_raw.png){width="800"}

=== "Difference of Hanning Convolution"
    ![image](../images/pipeline/extract/viewer_filter.png){width="800"}

=== "Smoothing"
    ![image](../images/pipeline/extract/viewer_smooth.png){width="800"}

From this, we see that away from the spots, the raw image has a non-zero intensity value (around 300). After
convolution with the difference of hanning kernel though, these regions become a lot darker (approximately 0). This
is because the sum of the difference of hanning kernel is 0 so its effect on a background region with a uniform 
non-zero value is to set it to 0.

Looking at the spots, we see that the convolution helps isolate the spots from the background and separate
spots which are close together. There is also a very dark (negative) region surrounding the spots. 
It is a feature of convolution with the difference of hanning kernel that it produces a negative annulus
about spots. This is because, the result of 

??? note "Why negative annulus is expected"

    The convolution in the annulus of a spot is like the sum of the multiplication of the spot line (yellow)
    with the kernel line (cyan). This multiplication produces the purple line, the sum of which is negative.

    ![image](../images/pipeline/extract/convolution.png){width="600"}

The smoothing in this example is only in the z direction (averaging over 3 z-planes: the one shown, 1 above and 1 below)
and seems to emphasise the spots and the negative annulus even more. 
This is because on one of the neighbouring z-planes, the spot has a larger intensity than on the z-plane shown so 
averaging increases the absolute intensity.

### Varying difference of hanning kernel radius
The below plots show the results of the convolution with the difference of hanning kernel for four different values
of `config['extract']['r1']`. In each case, `config['extract']['r2']` is twice this value.

=== "2"
    ![image](../images/pipeline/extract/r1=2.png){width="800"}

=== "3"
    ![image](../images/pipeline/extract/r1=3.png){width="800"}

=== "4"
    ![image](../images/pipeline/extract/r1=4.png){width="800"}

=== "6"
    ![image](../images/pipeline/extract/r1=6.png){width="800"}

From this, we see that with $r_1 = 2$, the background regions away from the spots appear less uniform than with
$r_1 = 3$ with quite a few patches of negative values. Also, the shape of the second spot from the left appears
distorted. These both indicate that the kernel is wanting to extract features smaller than those of interest.

As $r_1$ increases, we see that the negative annulus around becomes larger and eventually at $r_1=6$, the spots 
start merging together indicating the kernel is wanting to extract features larger than those of interest.

### Varying smoothing radius
The below plots show the results of the convolution with the difference of hanning kernel followed by smoothing
for four different values of `config['extract']['r_smooth']`. In each case, `config['extract']['r1'] = 3` and 
`config['extract']['r2'] = 6`.

=== "1, 1, 2"
    ![image](../images/pipeline/extract/r_smooth=112.png){width="800"}

=== "1, 1, 3"
    ![image](../images/pipeline/extract/r_smooth=113.png){width="800"}

=== "1, 1, 5"
    ![image](../images/pipeline/extract/r_smooth=115.png){width="800"}

=== "2, 2, 2"
    ![image](../images/pipeline/extract/r_smooth=222.png){width="800"}

=== "4, 4, 1"
    ![image](../images/pipeline/extract/r_smooth=441.png){width="800"}

From this, we see that smoothing in the z direction makes spots which appear most prominantly on other z-planes
appear much more intense in the z-plane shown. For example, the feature towards the bottom just to right of centre
is barely visible with `r_smooth = 1, 1, 2` but is clear with `r_smooth = 1, 1, 5`.

We also see that the difference between the `r_smooth = 1, 1, 2` and `r_smooth = 2, 2, 2` plots is barely perceivable.
This suggests that the z averaging is more important, this also makes sense seen as the convolution with the 
difference of hanning kernel is done in *2D* so treats each z-plane independently. In the `r_smooth = 4, 4, 1` image
with no z-averaging, we see that the spots have more of a gradual increase in intensity instead of a sharp peak.
