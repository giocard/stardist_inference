"""CLI for stardist_inference."""
import click
from . import io_utils
from . import stardist_functions
import os

__version__ = "1.2"

from .io_utils import get_filename_components


@click.command()
@click.option(
    "--image_path", "-i",
    type=click.Path(exists=True, dir_okay=True,readable=True),
    default=False,
    help="The path to the original raw intensity image(s) in klb/h5/tif/npy format with the same extensions respectively."
         "The path can be a directory with the files in subdirectories.",
)
@click.option(
    "--pixel_size_xyz", "-px", required=False, default="0.2,0.2,2", #type=click.FLOAT,
    help="Pixel size, in micrometers, along the three axes X, Y and Z. "
         "Used to rescale the data to the optimal size. "
         " Default: 0.2,0.2,2 (i.e., 0.2um in X and Y, 2um in Z).",
)
@click.option(
    "--output_dir","-o",
    type=click.Path(exists=True, dir_okay=True, readable=True),
    default=False,
    help="The output directory path.",
)
@click.option(
    "--early_model_dir", "-me", required=True,
    type=click.Path(exists=True, dir_okay=True, readable=True),
    help="The directory containing the trained Stardist 3D model for early stage of the embryo.",
)
@click.option(
    "--early_prob_thresh", "-pe", required=False, default=0.5, type=click.FLOAT,
    help="The probability threshold to be used to initialize the Stardist 3D model for early stage of the embryo.",
)
@click.option(
    "--early_nms_thresh", "-ne", required=False, default=0.3, type=click.FLOAT,
    help="The nms threshold to be used to initialize the Stardist 3D model for early stage of the embryo.",
)
@click.option(
    "--late_model_dir", "-ml", required=False,
    type=click.Path(exists=True, dir_okay=True, readable=True),
    default="False",
    help="The directory containing the trained Stardist 3D model for late stage of the embryo.",
)
@click.option(
    "--late_prob_thresh", "-pl", required=False, default=0.451, type=click.FLOAT,
    help="The probability threshold to be used to initialize the Stardist 3D model for late stage of the embryo..",
)
@click.option(
    "--late_nms_thresh", "-nl", required=False, default=0.5, type=click.FLOAT,
    help="The nms threshold to be used to initialize the Stardist 3D model for late stage of the embryo..",
)
@click.option(
    "--timepoint_switch", "-ts", required=True, type=click.INT,
    help="The time-point to switch from early to lae stage model.",
)
@click.option(
    "--output_format","-f", required=False, default="tif",
    type=click.Choice(["klb","h5","tif","npy"]),
    help="The output format klb/h5/tif/npy.",
)
@click.option(
    "--gen_roi","-gr", is_flag=True,
    help="Generate ROI files for segmentation correction.",
)
@click.option(
    "--no_8bit_shift","-no8sft", is_flag=True,
    help="Do not perform 8 bit shift when reading image.",
)
@click.version_option(version=__version__)
def main(
        image_path: str,
        pixel_size_xyz: str,
        output_dir: str,
        early_model_dir: str,
        early_prob_thresh: float,
        early_nms_thresh: float,
        late_model_dir: str,
        late_prob_thresh: float,
        late_nms_thresh: float,
        timepoint_switch: int,
        output_format: str,
        gen_roi: bool,
        no_8bit_shift: bool
) -> None:
    """Main entry point for stardist_inference."""

    # set the scale factors based on pixel size
    px, py, pz = [float(x) for x in pixel_size_xyz.split(',')]
    # scale images because models were trained with 0.2x0.2x2um data
    scale_factors = (pz/2.0, px/0.2, py/0.2)  # z,y,x
    print("Scale factors (z,y,x): ", scale_factors)

    # Load model
    early_model = stardist_functions.initialize_model(early_model_dir, early_prob_thresh, early_nms_thresh)

    late_model = stardist_functions.initialize_model(late_model_dir, late_prob_thresh, late_nms_thresh)

    if os.path.isdir(image_path):
        result = [os.path.join(dp, f)
                  for dp, dn, filenames in os.walk(image_path)
                  for f in filenames if (os.path.splitext(f)[1] == '.klb' or
                                         os.path.splitext(f)[1] == '.h5' or
                                         os.path.splitext(f)[1] == '.tif' or
                                         os.path.splitext(f)[1] == '.npy')]
        for image_file in result:
            print("Processing image:", image_file)
            file_base, file_prefix, file_ext, time_index = get_filename_components(image_file)
            Xi = io_utils.read_image(image_file, not no_8bit_shift)
            axis_norm = (0, 1, 2)  # normalize channels independently
            if (timepoint_switch >= 0 and time_index < timepoint_switch) or timepoint_switch == -1:
                print("Segmenting with early stage model.")
                label, detail = stardist_functions.run_3D_stardist(early_model,
                                                                   Xi, axis_norm, False,
                                                                   early_prob_thresh, early_nms_thresh,
                                                                   scale_factors)
            else:
                print("Segmenting with late stage model.")
                label, detail = stardist_functions.run_3D_stardist(late_model, Xi,
                                                                   axis_norm, False,
                                                                   late_prob_thresh, late_nms_thresh,
                                                                   scale_factors)

            out_image_name = os.path.splitext(os.path.basename(image_file))[0] + ".label"
            out_image_path = os.path.join(output_dir,out_image_name)
            io_utils.write_image(label, out_image_path, output_format, gen_roi)
    else:
        print("Processing image:", image_path)
        Xi = io_utils.read_image(image_path, not no_8bit_shift)
        axis_norm = (0, 1, 2)  # normalize channels independently
        label, detail = stardist_functions.run_3D_stardist(early_model, Xi, axis_norm, False,
                                                           early_prob_thresh, early_nms_thresh,
                                                           scale_factors)

        out_image_name = os.path.splitext(os.path.basename(image_path))[0] + ".label"
        out_image_path = os.path.join(output_dir,out_image_name)
        io_utils.write_image(label, out_image_path, output_format, gen_roi)

    print("Run successfully completed.")