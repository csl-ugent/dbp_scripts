#!/usr/bin/python3
import os
import pyexcel
import subprocess

# Import own modules
import config
import support

def get_binary_stripped_size(binary):
    output = os.path.join(config.tmp_dir, 'binary')
    subprocess.check_call(['strip', '--input-target', 'elf32-little', '-o', output, binary])
    return os.stat(output).st_size

def main():
    # Create the sheet
    print('************ Creating report on binary sizes **********')
    sheet = pyexcel.Sheet()
    rownames = [benchmark for benchmark,_ in support.benchmarks_gen()]
    sheet.column += ['Binary default'] + rownames + ['Binary diversified'] + rownames

    # Get all the sizes of the default binaries
    sizes = ['']
    for (benchmark, name) in support.benchmarks_gen():
        binary = os.path.join(support.create_path_for_seeds(config.build_dir), benchmark, name)
        if os.path.exists(binary):
            sizes.append(get_binary_stripped_size(binary))
        else:
            sizes.append('FAIL')

    # Create the AVG and MAX columns
    sheet.column += sizes + ['AVG'] + [''] * len(rownames)
    sheet.column += sizes + ['MAX'] + [''] * len(rownames)

    for seeds in support.all_seeds_gen():
        # Get all the sizes of the diversified binaries
        sizes = [''] * (len(rownames) +2)
        for (benchmark, name) in support.benchmarks_gen():
            binary = os.path.join(support.create_path_for_seeds(config.build_dir, *seeds), benchmark, name)
            if os.path.exists(binary):
                sizes.append(get_binary_stripped_size(binary))
            else:
                sizes.append('FAIL')

        sheet.column += sizes

    # Calculate in the average and the max
    for row in (row for row in sheet.rows() if not row[0].startswith('Binary')):
        sizes = [elem for elem in row[3:] if isinstance(elem, int)]
        if sizes:
            row[1] = sum(sizes) // len(sizes)
            row[2] = max(sizes)

    # Create the report book and write it out
    report = pyexcel.Book(sheets={'Sizes' : sheet})
    report.save_as(os.path.join(config.reports_dir, 'binary_sizes.ods'))

if __name__ == '__main__':
    main()
