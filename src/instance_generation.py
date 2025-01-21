#! /usr/bin/env python3

import argparse
import shutil
import subprocess
import sys
import tempfile

from collections import Counter
from math import log2

from clingo import Control
from clingo.solving import Model
from clingo.symbol import SymbolType
from collections import defaultdict
from pydantic import BaseModel
from typing import Dict, List, Optional

import asp_translator
import normalize
import pddl
import pddl_parser


def load_and_validate_extended_input(extended_input_file_path: str):
    # loads the extended input file (JSON) and checks if it has the correct
    # format (the basic format is defined by the ExtendedInput class)
    class ExtendedInput(BaseModel):
        universe: Dict[str, int]
        cardinality_constraints: Optional[Dict[str,List[int]]] = {}

    file = open(extended_input_file_path)
    data_string = '\n'.join(file.readlines())
    extended_input = dict(ExtendedInput.model_validate_json(data_string))
    for predicate_name, interval in \
            extended_input["cardinality_constraints"].items():
        if len(interval) != 2:
            print(f"Error: The list given as interval in the cardinality constraints for {predicate_name} has length {len(interval)} but must have length 2.")
            sys.exit(1)
    return extended_input


def create_instance(asp_model, model_number: int, domain: pddl.Domain):
    # builds the string of the PDDL instance that corresponds to the given ASP
    # model
    is_clingo_model = isinstance(asp_model, Model)
    if is_clingo_model:
        asp_atoms = [sym for sym in asp_model.symbols(shown=True)]
        assert(all(sym.type is SymbolType.Function for sym in asp_atoms))
        assert(all('_AT_' not in atom.name for atom in asp_atoms))
          # the Fast Downward translator creates helper predicates whose
          # translation to ASP contains '_AT_' but in the models of the answer
          # set program those predicates should not occur
    else: # from fasb we get the model as a string
        assert(isinstance(asp_model, str))
        asp_atoms = asp_model.split()

    # retrieve the PDDL objects (and their types) and the initial state atoms
    # from the atoms of the ASP model
    objects = defaultdict(set)
    initial_state = []
    pddl_type_names = [t.name.lower() for t in domain.types]
    for atom in asp_atoms:
        if is_clingo_model:
            atom_name = atom.name.replace(*('_DASH_', '-'))
            atom_arguments = atom.arguments
        else:
            if '(' in atom: # the atom has arguments
                atom_name = atom[:atom.index('(')].replace(*('_DASH_', '-'))
                  # removes everything starting at '(' (i. e. the arguments and
                  # the brackets) and replaces '_DASH_' with '-' (undoing the
                  # replacement from the ASP translator)
                atom_arguments = atom[atom.index('(')+1:-1].split(',')
                  # removes '(' and everything before and removes last element,
                  # then splits the remaining part (i. e., the arguments) on ','
            else: # the atom is nullary
                atom_name = atom.replace(*('_DASH_', '-'))
                atom_arguments = []
        if atom_name in pddl_type_names:
            # if the atom describes the type of an object, add that object and
            # that type to the objects-dictionary
            assert(len(atom_arguments) == 1)
            argument = atom_arguments[0]
            if is_clingo_model:
                object_string = f"obj_{argument.number}" if \
                        argument.type is SymbolType.Number else \
                        str(argument).replace(*('_DASH_', '-'))
            else:
                object_string = f"obj_{argument}" if argument.isdigit() else \
                        argument.replace(*('_DASH_', '-'))
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
            for arg in atom_arguments:
                if is_clingo_model:
                    argument_string = f"obj_{arg.number}" if \
                            arg.type is SymbolType.Number else \
                            str(arg).replace(*('_DASH_', '-'))
                else:
                    argument_string = f"obj_{arg}" if argument.isdigit() else \
                            argument.replace(*('_DASH_', '-'))
                arguments.append(argument_string)
            initial_state.append(f"({atom_name} {' '.join(arguments)})")

    typed_objects = []
    for obj, types in objects.items():
        base_type_names = [t.basetype_name.lower() for t in types if
                            t.basetype_name is not None]
        non_base_types = [t for t in types if t.name.lower() not in
                          base_type_names]
        assert(len(non_base_types) == 1)
          # an object can have only one type that is not a base type
        object_type = non_base_types[0]
        typed_objects.append(f"{obj} - {object_type.name.lower()}")

    assert(len(domain.functions) <= 1)
      # the instance generator does not handle functions except for action
      # costs
    has_action_costs = len(domain.functions) == 1
    instance_parts = []

    objects_string = "(:objects\n  " + '\n  '.join(typed_objects) + "\n)"
    instance_parts.append(objects_string)

    if has_action_costs:
        initial_state.insert(0, "(= (total-cost) 0)")
    initial_state_string = "(:init\n  " + '\n  '.join(initial_state) + "\n)"
    instance_parts.append(initial_state_string)

    goal = f"(:goal\n  {domain.goal.pddl_string()}\n)"
    instance_parts.append(goal)

    if has_action_costs:
        instance_parts.append("(:metric minimize (total-cost))")

    instance = f"(define (problem p{model_number})\n(:domain {domain.domain_name})\n" + '\n'.join(instance_parts) + "\n\n)"
    return instance


def shannon_entropy(atoms, models):
    # Shannon entropy of the atoms over the models
    # https://stackoverflow.com/questions/15450192/fastest-way-to-compute-entropy-in-python
    atom_occurences = [atom for model in models for atom in model if atom in atoms]
    atom_frequencies = Counter(atom_occurences)
    assert(0 not in atom_frequencies.values())
      # each atom must occur in at least one model
    probabilities = [float(freq) / atom_frequencies.total() for freq in
                     atom_frequencies.values()]
    entropy = sum([-prob*log2(prob) for prob in probabilities])
    return entropy


def representativeness(atoms, models):
    # computes how evenly the atoms are distributed among the models
    # value lies in (0,1]
    entropy = shannon_entropy(atoms, models)
    return 2**(entropy-log2(len(atoms)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
            "domain",
            help="PDDL domain file for which instances will be generated")
    arg_group = parser.add_mutually_exclusive_group(required=True)
    arg_group.add_argument("-n","--num_objects", type=int,
                        help="number of objects the instances will have")
    arg_group.add_argument("-e", "--extended_input",
                           help="JSON file specifying how many objects of which types the instances will have, and potentially constraints on how many atoms of a certain predicate there will be")
    parser.add_argument("num_instances", nargs='?', type=int, default=1,
                        help="maximum number of instances that will be generated (1 by default, 0 means all instances will be generated)")
    parser.add_argument("--representative", action="store_true",
                        help="generate a set of instances that is representative for the given domain")
    parser.add_argument("-o", "--output_file_prefix",
                        help="write generated instances to files whose names begin with the given prefix")
    parser.add_argument("--print_normalized_domain", action="store_true",
                        help="print the normalized PDDL domain")
    parser.add_argument("--print_translated_domain", action="store_true",
                        help="print the ASP program that the input PDDL domain is translated to")
    parser.add_argument("--print_asp_model", action="store_true",
                        help="print the model of the ASP program that corresponds to the input PDDL domain")
    args = parser.parse_args()

    domain = pddl_parser.open(args.domain)

    print("Normalizing axioms to Stratified Datalog")
    # TODO verify stratification?
    normalize.normalize_axioms(domain)
    if args.print_normalized_domain:
        print("Normalized PDDL domain:")
        domain.dump()
        print()

    print("Translating to ASP")
    if args.num_objects:
        universe = {"object": args.num_objects} # generic PDDL type "object"
        translated_domain = asp_translator.translate(domain, universe, {})
    else:
        extended_input = load_and_validate_extended_input(args.extended_input)
        universe = extended_input["universe"]
        constraints = extended_input["cardinality_constraints"]
        translated_domain = asp_translator.translate(domain, universe,
                                                     constraints)
    if args.print_translated_domain:
        print("ASP program of translated domain:")
        print(translated_domain)
        print()

    if args.num_instances < 0:
        print("Error: num_instances must be a non-negative number.")
        sys.exit(1)

    if args.representative:
        print("Calling ASP solver clingo")
#        ctl = Control([f"{args.num_instances}"])
        ctl = Control(["0"])
          # "0", i. e. "all models", because for cautious / brave consequences
          # clingo should consider all models
        ctl.add(translated_domain)
        ctl.ground()

        print("Calling clingo to compute cautious consequences")
        # cautious consequences are atoms that appear in every answer set of an
        # answer set program (i. e., atoms that will appear in every instance
        # of a domain)
        ctl.configuration.solve.enum_mode = "cautious"
        with ctl.solve(yield_ = True) as solve_handle:
            if not solve_handle.get().satisfiable:
                print(f"Clingo could not compute cautious consequences, reason: {solve_handle.get()}")
                sys.exit(1)
            cautious_consequences = []
              # overwrite this in every loop because only last computed model
              # contains the actual cautious consequences
            for model in solve_handle:
                cautious_consequences = model.symbols(shown=True)
                # TODO use atoms here (and analogously below) instead of shown?
                # soe uses shown

        print("Calling clingo to compute brave consequences")
        # brave consequences are atoms that appear in at least one answer set
        # of an answer set program (i. e., atoms that will appear in at least
        # one instance of a domain)
#        ctl = Control([f"{args.num_instances}"])
#        ctl.add(translated_domain)
#        ctl.ground()
        ctl.configuration.solve.enum_mode = "brave"
        with ctl.solve(yield_ = True) as solve_handle:
            if not solve_handle.get().satisfiable:
                print(f"Clingo could not compute brave consequences, reason: {solve_handle.get()}")
                sys.exit(1)
            brave_consequences = []
              # overwrite this in every loop because only last computed model
              # contains the actual brave consequences
            for model in solve_handle:
                brave_consequences = model.symbols(shown=True)

        # compute representative instances
        ctl.configuration.solve.enum_mode = "auto"
          # auto is the default value to compute answer sets
        target_atoms = [atom for atom in brave_consequences if atom not in
                        cautious_consequences]
          # we choose the facet inducing atoms as target atoms, i. e., the
          # atoms that appear in some answer set but not in all answer sets
        if not target_atoms:
              # brave_consequences == cautious_consequences, i. e., there is
              # exactly one answer set
            print("No facet inducing atoms, i. e., the domain characterization admits exactly one instance.")
#            ctl = Control([f"{args.num_instances}"])
#            ctl.add(translated_domain)
#            ctl.ground()
            with ctl.solve(yield_ = True) as solve_handle:
                if args.print_asp_model:
                    print(f"ASP model of instance:")
                    print(solve_handle.model())
                print(f"Creating instance from ASP model")
                instance = create_instance(solve_handle.model(), 1, domain)
                if args.output_file_prefix:
                    with open(f"{args.output_file_prefix}{model.number}.pddl",
                              "w") as f:
                        f.write(instance)
                        f.write("\n\n")
                else:
                    print(instance)
            sys.exit(0)
#        sieve_rule = f":- not {", not ".join([str(atom) for atom in target_atoms])}."
#          # :- not a1, not a2, not a3, ..., not an.
#          # ensures that each answer set includes at least one target atom
#          # TODO is this rule really useful? it gets subsumed by the rules
#          # added in each iteration
        model_number = 0
        to_cover = target_atoms.copy()
        models = []
        while to_cover:
            model_number += 1
            if args.num_instances > 0 and model_number > args.num_instances:
                # compute all possible instances if args.num_instances == 0,
                # otherwise compute at most args.num_instances instances
                break
            current_target = to_cover[0]
            # TODO choose current target atom according to more sophisticated
            # strategy than just using the first one?
#            ctl = Control([f"{args.num_instances}"])
#              # uses default "auto" for ctl.configuration.solve.enum_mode
#            ctl.add(translated_domain)
##            ctl.add(sieve_rule)
##            ctl.add(f":- not {current_target}.")
#            ctl.ground()
            with ctl.solve(yield_ = True, assumptions=[(current_target, True)]) \
                    as solve_handle:
                if solve_handle.get().satisfiable:
                    model = solve_handle.model()
                    # TODO choose model according to more sophisticated
                    # strategy than just using first one?
                    models.append(model.symbols(atoms=True))
                      # Model objects should not be accessed outside the
                      # with-block, so we store the atoms (of type Symbol)
                      # instead
                    if args.print_asp_model:
                        print(f"ASP model of instance number {model_number}:")
                        print(model)
                    print(f"Creating instance number {model_number} from ASP model")
                    instance = create_instance(model, model_number, domain)
                    if args.output_file_prefix:
                        with open(f"{args.output_file_prefix}{model_number}.pddl",
                                  "w") as f:
                            f.write(instance)
                            f.write("\n\n")
                    else:
                        print(instance)
                        print()
                    to_cover = [atom for atom in to_cover if atom not in
                                model.symbols(atoms=True)]
                      # all target atoms occuring in the current ASP model are
                      # covered and thus are removed from to_cover
                else:
                    # this should not be able to happen since there must be a
                    # solution for each facet-inducing atom (which are the
                    # target atoms)
                    print(f"Could not compute ASP model for current target atom '{str(current_target)}', reason: {solve_handle.get()}")
                    sys.exit(1)
        print(f"Finished generating {model_number} representative instances.")
        print(f"The representativeness score of the set of generated instances is {representativeness(target_atoms, models)}.")
######## old way to compute representative instances using fasb's mode soe as a
######## black box
#        if not shutil.which("fasb"):
#            print("Executable of fasb not found on PATH. For option --representative fasb must be on PATH.")
#            sys.exit(1)
#        with tempfile.NamedTemporaryFile(mode="w+t") as translated_domain_file:
#            with tempfile.NamedTemporaryFile(mode="w+t") as script_file:
#                # write the translated domain to a temporary file in
#                # preparation of calling fasb
#                translated_domain_file.write(translated_domain)
#                translated_domain_file.flush()
#                # write the script for the fasb call (the script contains a
#                # single line, calling mode soe)
#                script_file.write(":soe")
#                script_file.flush()
#                print("Calling fasb")
#                fasb_output = subprocess.run([shutil.which("fasb"), translated_domain_file.name, f"{args.num_instances}", script_file.name], capture_output=True, text=True)
#        if fasb_output.returncode != 0:
#            print("fasb exited with the following error message:")
#            print(fasb_output.stderr)
#            sys.exit(1)
#        # extract the models from the output of fasb (skip the first four lines
#        # and then every second line)
#        models = fasb_output.stdout.splitlines()[4::2]
#        model_number = 0
#        for model in models:
#            model_number += 1
#            if args.print_asp_model:
#                print(f"ASP model of instance number {model_number}:")
#                print(model)
#            print(f"Creating instance number {model_number} from ASP model")
#            instance = create_instance(model, model_number, domain)
#            if args.output_file_prefix:
#                with open(f"{args.output_file_prefix}{model_number}.pddl",
#                          "w") as f:
#                    f.write(instance)
#                    f.write("\n\n")
#            else:
#                print(instance)
#                print()
#        print("Finished generating representative instances.")
########
    else:
        print("Calling ASP solver clingo")
        ctl = Control([f"{args.num_instances}"])
        ctl.add(translated_domain)
        ctl.ground()
        with ctl.solve(yield_ = True) as solve_handle:
            for model in solve_handle:
                if args.print_asp_model:
                    print(f"ASP model of instance number {model.number}:")
                    print(model)
                print(f"Creating instance number {model.number} from ASP model")
                instance = create_instance(model, model.number, domain)
                if args.output_file_prefix:
                    with open(f"{args.output_file_prefix}{model.number}.pddl",
                              "w") as f:
                        f.write(instance)
                        f.write("\n\n")
                else:
                    print(instance)
                    print()
            if solve_handle.get().satisfiable:
                print("Finished generating instances.")
            elif solve_handle.get().unsatisfiable:
                print("The provided domain characterization is not satisfiable. No instance can be generated for it.")
            else:
                print("Failed to find a model for the provided domain characterization. Satisfiability unknown.")


if __name__ == "__main__":
    main()
