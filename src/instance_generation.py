#! /usr/bin/env python3

import sys

from clingo import Control

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
#    print(translated_domain)

    print("Calling clingo")
    ctl = Control()
#    ctl = Control(["0"]) # compute all models
    ctl.add(translated_domain)
    ctl.ground()
#    result = ctl.solve(on_model=print) # prints the model(s)
#    print(result) # prints whether satisfiable or unsatisfiable
    with ctl.solve(yield_ = True) as handle:
        for model in handle:
            print(model)
        print(handle.get()) # returns whether satisfiable or unsatisfiable

    # TODO translate clingo output back into original (PDDL) syntax and create
    # problem instance


if __name__ == "__main__":
    main()
