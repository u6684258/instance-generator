#! /usr/bin/env python3

import argparse
import json
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
    asp_atoms = [sym for sym in model.symbols(shown=True)]
    assert(all(sym.type is SymbolType.Function for sym in asp_atoms))
    assert(all('_AT_' not in atom.name for atom in asp_atoms))

    # retrieve the PDDL objects (and their types) and the initial state atoms
    # from the atoms of the ASP model
    objects = defaultdict(set)
    initial_state = []
    pddl_type_names = [t.name.lower() for t in domain.types]
    for atom in asp_atoms:
        atom_name = atom.name.replace(*('_DASH_', '-'))
        if atom_name in pddl_type_names:
            # if the atom describes the type of an object, add that object and
            # that type to the objects-dictionary
            assert(len(atom.arguments) == 1)
            argument = atom.arguments[0]
            object_string = f"obj_{argument.number}" if argument.type is SymbolType.Number else str(argument)
            object_type = pddl.Type("object")
            for t in domain.types:
                if atom_name == t.name.lower():
                    object_type = t
                    break
            objects[object_string].add(object_type)
        else:
            # else the atom is a basic predicate and thus is added to the
            # initial state
            arguments = []
            for arg in atom.arguments:
                argument_string = f"obj_{arg.number}" if arg.type is SymbolType.Number else str(arg)
                arguments.append(argument_string)
            initial_state.append(f"({atom_name} {' '.join(arguments)})")

    typed_objects = []
    for obj, types in objects.items():
        base_type_names = [t.basetype_name.lower() for t in types if
                            t.basetype_name is not None]
        non_base_types = [t for t in types if t.name.lower() not in
                          base_type_names]
        assert(len(non_base_types) == 1)
          # an object can have only one type that is not a super type (base type)
        object_type = non_base_types[0]
        typed_objects.append(f"{obj} - {object_type.name.lower()}")

    assert(len(domain.functions) <= 1)
      # the instance generator does not handle functions except for action
      # costs
    has_action_costs = len(domain.functions) == 1
    instance_parts = []

    objects_string = f"(:objects\n  {'\n  '.join(typed_objects)}\n)"
    instance_parts.append(objects_string)

    if has_action_costs:
        initial_state.insert(0, "(= (total-cost) 0)")
    initial_state_string = f"(:init\n  {'\n  '.join(initial_state)}\n)"
    instance_parts.append(initial_state_string)

    goal = f"(:goal\n  {domain.goal.pddl_string()}\n)"
    instance_parts.append(goal)

    if has_action_costs:
        instance_parts.append("(:metric minimize (total-cost))")

    instance = f"(define (problem p{model.number})\n\n(:domain {domain.domain_name})\n{'\n'.join(instance_parts)}\n\n)"
    return instance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
            "domain",
            help="PDDL domain file for which instances will be generated")
    arg_group = parser.add_mutually_exclusive_group(required=True)
    arg_group.add_argument("-n","--num_objects", type=int,
                        help="number of objects the instances will have")
    arg_group.add_argument("-t", "--typed_universe",
                           help="JSON file specifying how many objects of which types the instances will have")
    parser.add_argument("num_instances", nargs='?', type=int, default=1,
                        help="maximum number of instances that will be generated (1 by default, 0 means all instances will be generated)")
    parser.add_argument("-o", "--output_file_prefix",
                        help="write generated instances to files whose names begin with the given prefix")
    args = parser.parse_args()

    domain = pddl_parser.open(args.domain)
#    domain.dump()
#    print()

    print("Normalizing axioms to Stratified Datalog")
    # TODO verify stratification?
    normalize.normalize_axioms(domain)
#    domain.dump()

    print("Translating to ASP")
    if args.num_objects:
        universe_size = args.num_objects
        translated_domain = asp_translator.translate_by_size(domain,
                                                             universe_size)
    else:
        file = open(args.typed_universe)
        typed_universe = json.load(file)
        # TODO verify that typed_universe has correct form? i. e. each key is
        # string, each entry has single item which is int
        translated_domain = asp_translator.translate_by_universe(domain,
                                                                 typed_universe)
#    print(translated_domain)

    if args.num_instances < 0:
        print("Error: num_instances must be a non-negative number.")
        sys.exit(1)
    print("Calling clingo")
    ctl = Control([f"{args.num_instances}"])
#    ctl = Control(["0"]) # compute all models
    ctl.add(translated_domain)
    ctl.ground()
    with ctl.solve(yield_ = True) as handle:
        for model in handle:
#            print(model)
            print(f"Creating instance number {model.number} from ASP model")
            instance = create_instance(model, domain)
            if args.output_file_prefix:
                with open(f"{args.output_file_prefix}{model.number}.pddl",
                          "w") as f:
                    f.write(instance)
                    f.write("\n\n")
            else:
                print(instance)
                print()
        if handle.get().satisfiable:
            print("Finished generating instances.")
        elif handle.get().unsatisfiable:
            print("The provided domain characterization is not satisfiable.")
        else:
            print("Failed to find a model for the provided domain characterization. Satisfiability unknown.")


if __name__ == "__main__":
    main()
