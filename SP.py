import glob
import os
import subprocess

# Import own modules
import config
import support
from seed import AbstractSeed

class SPSeed(AbstractSeed):
    """The class for SP seeds"""
    idx = len(AbstractSeed.__subclasses__())

    # Static variables
    default_compile_options = ['-mllvm', '-stackpadding=' + str(config.default_padding)]
    opportunity_log = 'stackpadding.list'

    def compile_options_for_padding(padding):
        return ['-mllvm', '-stackpadding=' + str(padding)]

    def diversify_build(seed):
        return ['-mllvm', '-stackpadding=' + str(config.max_padding), '-mllvm', '-padseed=' + str(seed)]

    def replay(seed, base_symfile, base_data):
        print('************ Replaying stack padding. **********')

        # Use the replay tool to find the stack offset for every function. We do a replay for the
        # opportunity log of the actual build, and also of that for every extra (shared) artefact.
        sections = {}
        seed.run_replay_tool(sections, os.readlink(os.path.join(base_data, 'build')), os.path.join(base_data, seed.opportunity_log))
        shared_base_data = os.path.dirname(base_data)
        for build_prefix in glob.glob(os.path.join(shared_base_data, 'build.*')):
            suffix = build_prefix[build_prefix.rfind('.'):]
            seed.run_replay_tool(sections, os.readlink(build_prefix), os.path.join(os.path.dirname(base_data), seed.opportunity_log + suffix))

        for func in base_symfile.funcs:
            # Get the stack offset introduced
            offset = sections.get(func.section_name, 0)

            if offset:
                base_record = func.get_stack_offset_record()
                # This record may very well not exist, such as when a frame pointer is used.
                if base_record:
                    base_record.set_frame_size(base_record.get_frame_size() + offset - config.default_padding)

    def run_replay_tool(seed, sections, build_prefix, opportunity_log):
        for line in subprocess.check_output([os.path.join(config.replay_dir, 'sp'), str(seed), str(config.max_padding),
            build_prefix, opportunity_log], universal_newlines=True).splitlines():

            # Split the line and decode the tokens
            tokens = line.split()
            name = tokens[0]
            offset = int(tokens[1])

            # Add the section with the introduced diff
            assert name not in sections, 'Duplicate section!'
            sections[name] = offset
