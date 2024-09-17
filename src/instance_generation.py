#! /usr/bin/env python3

import sys

from clingo import Control
from clingo.solving import Model
from clingo.symbol import SymbolType
from collections import defaultdict

import asp_translator
import normalize
import pddl
import pddl_parser


def create_instance(model: Model, domain: pddl.Domain):
    # TODO differentiate between types and other basic atoms; use the types for
    # the specification of the objects
    # TODO add the two fixed lines if action-costs are included; identify this
    # by looking at domain.functions (assert len <= 1 and if == 1 add the two
    # lines)
    asp_atoms = [sym for sym in model.symbols(shown=True)]
    assert(all(sym.type is SymbolType.Function for sym in asp_atoms))
    assert(all('_AT_' not in atom.name for atom in asp_atoms))

#    instance = []
#    for atom in asp_atoms:
#        atom_name = atom.name.replace(*('_DASH_', '-'))
#        atom_args = []
#        for arg in atom.arguments:
#            if arg.type is SymbolType.Number:
#                atom_args.append(f"obj_{arg.number}")
#            else:
#                atom_args.append(str(arg))
#        instance.append(f"name: {atom_name}, args: {', '.join(atom_args)}")
#    return "\n".join(instance)
    instance_parts = []
    objects = defaultdict(set)
    initial_state = []
    pddl_type_names = [t.name.lower() for t in domain.types]
    # TODO replace dash when processing atom
    for atom in asp_atoms:
        atom_name = atom.name.replace(*('_DASH_', '-'))
        if atom_name in pddl_type_names:
            # if the atom describes the type of an object, add that object and
            # the type to the objects-dictionary
            assert(len(atom.arguments) == 1)
            argument = atom.arguments[0]
            argument_string = f"obj_{argument.number}" if argument is SymbolType.Number else str(argument)
            objects[argument_string].add(atom_name)
        # TODO else add the atom to the initial state
            

    # TODO for all objects: set object's type to the one that is no basetype of
    # any type mentioned for this object

    objects_string = f"(:objects)" # TODO
    instance_parts.append(objects_string)

    initial_state_string = f"(:init)" # TODO implement and add line (= (total-cost) 0) if have action costs
    instance_parts.append(initial_state_string)

    goal = f"(:goal)"# TODO add domain.goal
    # TODO add string methods to Condition etc. for this (can probably reuse code from dump-methods)
    instance_parts.append(goal)

    # TODO if action-costs: instance_parts.append(metric)

    instance = f"(define (problem p{model.number})\n(:domain {domain.domain_name})\n{'\n'.join(instance_parts)}\n)"
    return instance


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

    print("Calling clingo")
    ctl = Control()
#    ctl = Control(["0"]) # compute all models
    ctl.add(translated_domain)
    ctl.ground()
    with ctl.solve(yield_ = True) as handle:
        for model in handle:
            print(model)
            print(f"Creating instance number {model.number} from ASP model")
            print(create_instance(model, domain))
        if handle.get().satisfiable:
            print("Finished generating instances.")
        elif handle.get().unsatisfiable:
            print("The provided domain characterization is not satisfiable.")
        else:
            print("Failed to find a model for the provided domain characterization. Satisfiability unknown.")


if __name__ == "__main__":
    main()
