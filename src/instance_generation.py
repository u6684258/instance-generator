#! /usr/bin/env python3

import sys

import asp_translator
import normalize
import pddl
import pddl_parser

def main():
    if len(sys.argv) != 3:
        print("Usage: instance_generation.py <domain-file> <universe-size>")
        sys.exit(1)
    if not sys.argv[2].isdigit():
        print("Second argument <universe-size> must be a positive integer.")
        sys.exit(1)

    domain_file = sys.argv[1]
    universe_size = int(sys.argv[2])
    domain = pddl_parser.open(domain_file)
#    domain.dump()
#    print()

    print("Normalizing axioms to Stratified Datalog")
    # TODO verify stratification?
    normalize.normalize_axioms(domain)
#    domain.dump()

    print("Translating to ASP")
    translated_domain = asp_translator.translate(domain, universe_size)
    print(translated_domain)
    # TODO call clingo
    # TODO translate clingo output back into original (PDDL) syntax



if __name__ == "__main__":
    main()
