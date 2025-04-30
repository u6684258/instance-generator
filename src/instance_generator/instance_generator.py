#! /usr/bin/env python3

import argparse
from collections import Counter, defaultdict
from enum import Enum
from math import log2
import sys
from typing import Dict, List, Optional

from clingo import Control
from clingo.symbol import Symbol, SymbolType
from pydantic import BaseModel

from . import asp_translator
from . import pddl
from . import pddl_parser
from . import profiling
from .axiom_normalizer import normalize_axioms


def get_command_line_arguments():
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
                        help="for each generated instance print the ASP model it is based on (including derived predicates and helper predicates from the Fast Downward translator)")
    return parser.parse_args()


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
            print(f"The list given as interval in the cardinality constraints for {predicate_name} has length {len(interval)} but must have length 2.")
            sys.exit(1)
    return extended_input


# translation functions to get from ASP back to PDDL

def translate_to_atom_name_and_arguments(atom, is_clingo_symbol: bool):
    if is_clingo_symbol:
        atom_name = atom.name.replace(*('_DASH_', '-'))
        atom_arguments = atom.arguments
    else:
        if '(' in atom: # the atom has arguments
            atom_name = atom[:atom.index('(')].replace(*('_DASH_', '-'))
              # removes everything starting at '(' (i. e. the arguments and
              # the brackets) and replaces '_DASH_' with '-' (undoing the
              # replacement from the ASP translator)
            atom_arguments = atom[atom.index('(')+1:-1].split(',')
              # removes '(' and everything before and removes the last
              # element (which is the closing bracket ')'), then splits the
              # remaining part (i. e., the arguments) on ','
        else: # the atom is nullary
            atom_name = atom.replace(*('_DASH_', '-'))
            atom_arguments = []
    return atom_name, atom_arguments


def translate_to_object_string(obj, is_clingo_symbol: bool):
    if is_clingo_symbol:
        return f"obj_{obj.number}" if obj.type is SymbolType.Number else \
                str(obj).replace(*('_DASH_', '-'))
    else:
        return f"obj_{obj}" if obj.isdigit() else \
                obj.replace(*('_DASH_', '-'))


def translate_to_pddl_type(type_name: str, domain: pddl.Domain):
    for t in domain.types:
        if type_name == t.name.lower():
            return t
    assert(type_name == "object")
    return pddl.Type("object")


def extract_objects_and_initial_state(asp_model, domain: pddl.Domain):
    # retrieve the PDDL objects (and their types) and the initial state atoms
    # from the atoms of the ASP model
    # extracting the objects and the initial state is combined into one
    # function to avoid iterating twice through the atoms of the ASP model
    is_clingo_model = all(isinstance(atom, Symbol) for atom in asp_model)
    if is_clingo_model:
        asp_atoms = [sym for sym in asp_model]
        assert(all(sym.type is SymbolType.Function for sym in asp_atoms))
        assert(all('_AT_' not in atom.name for atom in asp_atoms))
          # the Fast Downward translator creates helper predicates whose
          # translation to ASP contains '_AT_' but in the models of the answer
          # set program those predicates should not occur
    else:
        assert(isinstance(asp_model, str))
        assert('__AT__' not in asp_model)
        asp_atoms = asp_model.split()

    objects = defaultdict(set)
      # for gathering the objects and all PDDL types each object has according
      # to the ASP model
    initial_state = []
    pddl_type_names = [t.name.lower() for t in domain.types]
    for atom in asp_atoms:
        atom_name, atom_arguments = translate_to_atom_name_and_arguments(
                atom, is_clingo_model)
        if atom_name in pddl_type_names:
            # if the atom describes the type of an object, add that object and
            # that type to the objects-dictionary
            assert(len(atom_arguments) == 1)
            argument = atom_arguments[0]
            object_string = translate_to_object_string(argument, is_clingo_model)
            object_type = translate_to_pddl_type(atom_name, domain)
            objects[object_string].add(object_type)
        else:
            # else the atom is a basic predicate and thus is added to the
            # initial state
            arguments = []
            for arg in atom_arguments:
                argument_string = translate_to_object_string(arg, is_clingo_model)
                arguments.append(argument_string)
            initial_state.append(f"({atom_name} {' '.join(arguments)})")

    typed_objects = []
    # attach the type to each object that is not a base type of the object
    for obj, types in objects.items():
        base_type_names = [t.basetype_name.lower() for t in types if
                            t.basetype_name is not None]
        non_base_types = [t for t in types if t.name.lower() not in
                          base_type_names]
        assert(len(non_base_types) == 1)
          # an object can have only one type that is not a base type
        object_type = non_base_types[0]
        typed_objects.append(f"{obj} - {object_type.name.lower()}")
    return typed_objects, initial_state


def create_instance(asp_model, model_number: int, domain: pddl.Domain):
    # builds the string of the PDDL instance that corresponds to the given ASP
    # model
    instance_parts = []

    objects, initial_state = extract_objects_and_initial_state(
            asp_model, domain)

    objects_string = "(:objects\n  " + '\n  '.join(objects) + "\n)"
    instance_parts.append(objects_string)

    assert(len(domain.functions) <= 1)
      # the instance generator does not handle functions except for action
      # costs
    has_action_costs = len(domain.functions) == 1

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


class ConsequencesType(Enum):
    BRAVE = 1
    CAUTIOUS = 2


def get_consequences(ctl: Control, consequences_type: ConsequencesType):
    # computes the brave or cautious consequences of the grounded answer set
    # program used in ctl
    # - brave consequences are atoms that appear in at least one answer set of
    #   an answer set program (i. e., atoms that will appear in at least one
    #   instance of a domain)
    # - cautious consequences are atoms that appear in every answer set of an
    #   answer set program (i. e., atoms that will appear in every instance of
    #   a domain)
    num_models_backup = ctl.configuration.solve.models
    ctl.configuration.solve.models = 0
      # according to clingo's documentation to compute brave or cautious
      # consequences clingo must be allowed to compute all models
    solve_mode_backup = ctl.configuration.solve.enum_mode
    ctl.configuration.solve.enum_mode = consequences_type.name.lower()
    with ctl.solve(yield_ = True) as solve_handle:
        model = solve_handle.model()
        if model is None:
            print(f"Clingo could not compute {consequences_type.name.lower()} consequences, reason: {solve_handle.get()}")
            sys.exit(1)
        for model in solve_handle:
            # only the last computed model contains the actual consequences
            pass
        consequences = model.symbols(shown=True)
        # TODO use atoms here instead of shown? soe uses shown
    # clean up
    ctl.configuration.solve.models = num_models_backup
    ctl.configuration.solve.enum_mode = solve_mode_backup
    return consequences


def shannon_entropy(atoms, atom_frequencies: Counter):
    # Shannon entropy of the atoms given their frequencies
    # https://stackoverflow.com/questions/15450192/fastest-way-to-compute-entropy-in-python
    probabilities = [float(freq) / atom_frequencies.total() for freq in
                     atom_frequencies.values()]
    entropy = sum([-prob*log2(prob) for prob in probabilities])
    return entropy


def representativeness(atoms, atom_frequencies):
    # computes how evenly the atoms are distributed,
    # value lies in (0,1]
    entropy = shannon_entropy(atoms, atom_frequencies)
    return 2**(entropy-log2(len(atoms)))


def get_asp_models(translated_domain, num_instances: int, representative: bool):
    # returns a generator yielding tuples of the form (model, full_model) where
    # full_model contains all atoms of the ASP model while model only contains
    # those atoms that are relevant for creating an instance from it

    if representative:
        with profiling.profiling("Setting up ASP solver clingo"):
            ctl = Control(["0"])
              # "0", i. e. "all models", because for cautious / brave consequences
              # clingo needs to consider all models
            ctl.add(translated_domain)
            ctl.ground()

        with profiling.profiling("Calling clingo to compute brave consequences"):
            brave_consequences = get_consequences(ctl, ConsequencesType.BRAVE)

        with profiling.profiling("Calling clingo to compute cautious consequences"):
            cautious_consequences = get_consequences(ctl,
                                                     ConsequencesType.CAUTIOUS)

        # representativeness is determined in terms of a set of target atoms
        target_atoms = [atom for atom in brave_consequences if atom not in
                        cautious_consequences]
          # we choose the facet inducing atoms as target atoms, i. e., the
          # atoms that appear in some answer set but not in all answer sets
        if not target_atoms:
              # brave_consequences == cautious_consequences, i. e., there is
              # exactly one answer set
            print("No facet-inducing atoms were found, thus the domain characterization admits exactly one instance.")
            with profiling.profiling("Calling clingo to compute the only ASP model"):
                with ctl.solve(yield_ = True) as solve_handle:
                    model = solve_handle.model()
                    if model is None:
                        print(f"Clingo could not compute the ASP model, reason: {solve_handle.get()}")
                        sys.exit(1)
                    yield (model.symbols(shown=True), model.symbols(atoms=True))
        else:
            with profiling.profiling("Calling clingo to compute representative ASP models", block=True):
#                sieve_rule = f":- not {", not ".join([str(atom) for atom in target_atoms])}."
#                  # :- not a1, not a2, not a3, ..., not an.
#                  # ensures that each answer set includes at least one target atom
#                  # TODO is this rule really useful? it gets subsumed by the rules
#                  # added in each iteration
                current_model_number = 0
                to_cover = target_atoms.copy()
                atom_frequencies = Counter()
                  # counts in how many generated ASP models each target atom occurs
                while to_cover:
                    current_model_number += 1
                    if num_instances > 0 and current_model_number > num_instances:
                        break
                        # compute all possible ASP models if num_instances ==
                        # 0, otherwise compute at most num_instances ASP
                        # models
                    current_target = to_cover[0]
                    # TODO choose current target atom according to more sophisticated
                    # strategy than just using the first one?
#                    ctl = Control([f"{num_instances}"])
#                    ctl.add(translated_domain)
##                    ctl.add(sieve_rule)
##                    ctl.add(f":- not {current_target}.")
#                    ctl.ground()
                    with ctl.solve(yield_ = True, assumptions=[(current_target, True)]) \
                            as solve_handle:
                        model = solve_handle.model()
                        # TODO choose model according to more sophisticated
                        # strategy than just using first one?
                        assert(not model is None)
                          # by definition of facet-inducing atoms, at least one ASP
                          # model must exist for each facet-inducing atom (which
                          # are the target atoms)
                        yield (model.symbols(shown=True), model.symbols(atoms=True))

                        # update atom_frequencies based on newly generated ASP model
                        for atom in target_atoms:
                            if atom in model.symbols(atoms=True):
                                atom_frequencies[atom] += 1

                        # all target atoms occuring in the current ASP model are
                        # covered and thus we remove them from to_cover
                        to_cover = [atom for atom in to_cover if atom not in
                                    model.symbols(atoms=True)]
                # (This part of the function will be executed eventually because in
                # the caller we use a for-loop over the generator returned by this
                # function.)
                print(f"The representativeness score of the set of generated ASP models is {representativeness(target_atoms, atom_frequencies)}")
    else: # representative == False
        with profiling.profiling("Setting up ASP solver clingo"):
            ctl = Control([f"{num_instances}"])
            ctl.add(translated_domain)
            ctl.ground()
        if num_instances > 0:
            msg = f"Calling clingo to compute up to {num_instances} ASP models"
        else:
            msg = "Calling clingo to compute all possible ASP models"
        with profiling.profiling(msg, block=True):
            with ctl.solve(yield_ = True) as solve_handle:
                model = solve_handle.model()
                if model is None:
                    print(f"Clingo could not compute the ASP models, reason: {solve_handle.get()}")
                    sys.exit(1)
                yield (model.symbols(shown=True), model.symbols(atoms=True))
                for model in solve_handle:
                    yield (model.symbols(shown=True), model.symbols(atoms=True))


def main():
    timer = profiling.Timer()
    memory_measurement = profiling.MemoryMeasurement()

    args = get_command_line_arguments()
    domain = pddl_parser.open(args.domain)

    with profiling.profiling("Normalizing axioms to Stratified Datalog"):
        # TODO verify stratification?
        normalize_axioms(domain)
        if args.print_normalized_domain:
            print("Normalized PDDL domain:")
            domain.dump()
            print()

    with profiling.profiling("Translating to ASP"):
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
        print(f"num_instances must be a non-negative number but is {args.num_instances}.")
        sys.exit(1)

    with profiling.profiling("Generating instances", block=True):
        instance_number = 0
        for (model, full_model) in get_asp_models(translated_domain,
                                                  args.num_instances,
                                                  args.representative):
            instance_number += 1
            if args.print_asp_model:
                print(f"ASP model of instance number {instance_number}:")
                print(full_model)
            instance = create_instance(model, instance_number, domain)
            if args.output_file_prefix:
                with open(f"{args.output_file_prefix}{instance_number}.pddl",
                          "w") as f:
                    f.write(instance)
                    f.write("\n\n")
            else:
                print(f"Instance number {instance_number}:")
                print(instance)
                print()
    print(f"Finished generating {instance_number} instances")
    print(f"Runtime: {timer}")
    print(f"Memory: {memory_measurement}")


if __name__ == "__main__":
    main()

