# ∆Breakpad

## Requirements & Installation
To execute the scripts in this repository we require:
- Python 3.3
- Python modules: pyexcel pyexcel-ods3 python-gnupg

Repositories:
- breakpad
- Diablo regression

## Configuration
The configuration can be done in the config.py file. The things that can be set here are certain parameters for the protections and testing environment, and the paths to repositories and tools that are required.

## Recreating tests
The tests can be recreated using the generate_all_results.py script. When invoked with arguments it generates results using these as compilation arguments, else it generates results for every combination of compilation flags. It generates data by invoking these scripts in order:
- init.py: Does some initialization such as creating a logfile and generating seeds.
- build_binaries.py: Build the binaries, with protections.
- link_binaries.py: Apply the protections that are implemented at linker level.
- extract_data.py: Extract all the data (symfiles and others) that is required to generate the patches.
- create_patches.py: Creates the patches for all binaries and different combinations of protections. The patches are immediately tested for correctness.
- inject_delta_data.py: Creates the ∆data and injects it into the binaries.

Reports on the generated data are then generated (in the ODS format) using these scripts:
- report_binary_sizes.py: The sizes of the default and fully diversified binaries (all stripped).
- report_binary_text_sizes.py: The sizes of the .text sections of the default and fully diversified binaries.
- report_delta_data_sizes.py: The sizes of the ∆data.
- report_opportunity_log_sizes.py: The sizes of the opportunity logs.
- report_patch_sizes.py: The sizes of the patches for all the combinations of the diversifications.
- report_patch_timing.py: This script times how long it takes to generate and apply patches for fully diversified binaries.
- report_symfile_sizes.py: The sizes of the symfiles for the default and fully diversified binaries.

Some other scripts of note are:
- setup.py: Does the general setup for ∆Breakpad, creating a directory structure and building helper binaries.
- measure_defaults.py: Can be used to generate a lot of measurements on the default binaries with the breakpad client but without any protections.
- measure_sp_function_sizes.py: Can be used to measure the increase/decrease in function sizes for different amounts of stack padding.
- patch.py: Can be used to create individual patches between symfiles.
- regression_binaries.py: Regression tests the protected binaries.
