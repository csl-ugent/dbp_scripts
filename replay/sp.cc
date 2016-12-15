#include <cstdint>
#include <fstream>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <unordered_map>

/* Include the LLVM header required to get the hashing functions */
#include "llvm/ADT/Hashing.h"

int main(int argc, char** argv) {
  /* Decode arguments */
  if (argc != 5) {
    std::cerr << "ARGUMENTS: ./binary <seed> <padding> <build_dir> <file>" << std::endl;
    return -1;
  }
  const uint32_t seed = std::stoul(argv[1]);
  const uint32_t padding = std::stoul(argv[2]);
  const std::string& build_dir = argv[3];
  std::uniform_int_distribution<unsigned> distribution(1, padding/8);
  std::unordered_map<std::string, std::mt19937> generators;

  /* Open file and read line per line */
  std::ifstream input(argv[4]);
  std::string line;
  while (std::getline(input, line)) {
    /* Get the names from the line */
    std::istringstream iss(line);
    std::string filename, function_name;
    iss >> filename >> function_name;

    /* Get the generator for this filename (only constructed the first time, so the seeds are generated correctly) */
    std::mt19937& generator = generators.emplace(filename, std::mt19937((unsigned)seed ^ llvm::hash_value(filename.substr(1 + filename.find_last_of('/'))))).first->second;

    /* Generate the offset */
    unsigned stack_offset = distribution(generator) * 8;

    /* Adapt and combine the filename and function name to look like obj_name:section_name */
    size_t i = filename.rfind('.');
    filename.replace(i + 1, filename.length(), "o");
    if (function_name.find("_GLOBAL__sub_I_") == 0)/* Startup sections have functions with a weird prefix */
        function_name = "startup";
    std::cout << build_dir << "/" << filename << ":.text." << function_name << " " << stack_offset << std::endl;
  }
  input.close();
}
