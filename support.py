import itertools
import os
import random
import shutil
import subprocess

# Local config
import config
import seed

# Aligns x to base (21, 16) -> 32
def align(x, base):
    offset = x % base
    if offset == 0:
        return x
    else:
        return x + (base - offset)

def hex_int(x):
    return int(x, 16)

def hex_str(x):
    return format(x, 'x')

# We can input seed tuples on the command line through a comma-separated list. If an element is missing it's presumed to be the default seed.
def seed_tuple(s):
    tokens = s.split(',')
    types = seed.get_types()
    assert len(tokens) == len(types), 'The number of seeds on the command line differ from the number of protections.'

    # First convert the tokens to integers, then create the actual seeds
    int_seeds = [int(token) if token else 0 for token in tokens]
    return [cls(s) for cls, s in zip(types, int_seeds)]

# For every type, get from the tuple an instance or a default seed
def get_seeds_from_tuple(seed_tuple, *types):
    ret = []
    for t in types:
        found = False
        for s in seed_tuple:
            if isinstance(s, t):
                found = True
                ret.append(s)
                break

        # If we haven't found any instance of t, create a default one
        if not found:
            ret.append(t(0))
    return ret

def find_first_uppercase(x):
    for (idx, char) in enumerate(x):
        if char.isupper():
            return idx
    return -1

# Generator for all the benchmark names
def benchmarks_gen():
    for benchmark in ['400.perlbench','401.bzip2','403.gcc','429.mcf','433.milc','444.namd','445.gobmk','450.soplex','453.povray','456.hmmer','458.sjeng','462.libquantum','464.h264ref','470.lbm','471.omnetpp','473.astar','482.sphinx3','483.xalancbmk','998.specrand']:
        name = benchmark.split('.')[1]
        if benchmark == '482.sphinx3':
            name = 'sphinx_livepretend'
        elif benchmark == '483.xalancbmk':
            name = 'Xalan'
        elif benchmark == '998.specrand':
            continue
        yield (benchmark, name)

# Generator for the seeds, gets the seeds from a random seed file.
# Returns a list containing one seed of every type.
def seeds_gen(*types):
    with open(config.seed_file, 'r') as f:
        seeds = [int(line.rstrip()) for line in f]
        assert len(seeds) % seed.nr_of_types == 0, 'The number of seeds in the file should be a multiple of ' + str(seed.nr_of_types) + '.'
        for iii in range(len(seeds) // seed.nr_of_types):
            yield [cls(seeds[(seed.nr_of_types * iii) + cls.idx]) for cls in types]

# Generator for the seeds, of all types.
def all_seeds_gen():
    for s in seeds_gen(*seed.get_types()):
        yield s

# Generate the subsets of all sizes for a certain set (with or without the empty subset).
def subsets_gen(s, empty=True):
    for l in range(0 if empty else 1, len(s) +1):
        for subset in itertools.combinations(s, l):
            yield subset

# Generate the subsets of all sizes for all build-time protections in a set
def build_subsets_gen(s, empty=True):
    s = [i for i in s if hasattr(i, 'diversify_build') ]
    for l in subsets_gen(s, empty):
        yield l

# Generate the subsets of all sizes for all link-time protections in a set
def link_subsets_gen(s, empty=True):
    s = [i for i in s if hasattr(i, 'diversify_link') ]
    for l in subsets_gen(s, empty):
        yield l

# This function generates the required number of seeds and writes them in the seed file
def generate_seeds(nr_of_tuples, root_seed):
    # Seed the PRNG and open the seed file (is truncated)
    random.seed(root_seed)
    with open(config.seed_file, 'w') as f:
        for _ in range(seed.nr_of_types * nr_of_tuples):
            s = (random.randint(1, config.max_seed))
            f.write(str(s) + '\n')

# Create the relpath for a certain seed combination.
def relpath_for_seeds(*seeds):
    args = ['0'] * seed.nr_of_types
    for s in seeds:
        args[s.idx] = str(s)
    return os.path.join(*args)

# Create the path for a certain seed combination (starting from a base path).
def create_path_for_seeds(base_path, *seeds):
    return os.path.join(base_path, relpath_for_seeds(*seeds))

# Update the regression scripts in the target directory, presuming that the benchmarks (and reference inputs and such) are already present.
def update_spec_regression(target_dir):
    subprocess.check_call([config.spec2regression_script, '-n', '-s', config.ssh_params, '-p', config.spec_dir, '-t', '5000', '-d', target_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Copy over existing benchmark spec tree and update the regression scripts
def copy_spec_tree(src, dst):
    shutil.rmtree(dst, True)
    shutil.copytree(src, dst)
    update_spec_regression(dst)

# Get the object name, in a general manner
def get_objname(name):
    # For the absolute paths used for the artefacts that were built extra:
    # Remove the extra_build directory prefix.
    if name.startswith(create_path_for_seeds(config.extra_build_dir)):
        name = os.path.join(config.extra_build_dir, '*', os.path.relpath(name, create_path_for_seeds(config.extra_build_dir)))

    # Disregard the archive information: arch.a(obj.o) => obj.o
    if '(' in name:
        name = name[name.index('(') +1: name.index(')')]

    return name
