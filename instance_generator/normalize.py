#! /usr/bin/env python3

import copy
from typing import Sequence

from instance_generator import pddl

class ConditionProxy:
    def clone_owner(self):
        clone = copy.copy(self)
        clone.owner = copy.copy(clone.owner)
        return clone

class AxiomConditionProxy(ConditionProxy):
    def __init__(self, axiom):
        self.owner = axiom
        self.condition = axiom.condition
    def set(self, new_condition):
        self.owner.condition = self.condition = new_condition
    def register_owner(self, domain):
        domain.axioms.append(self.owner)
    def delete_owner(self, domain):
        domain.axioms.remove(self.owner)
    def get_type_map(self):
        return self.owner.type_map


def get_axiom_predicate(axiom):
    name = axiom
    variables = [par.name for par in axiom.parameters]
    if isinstance(axiom.condition, pddl.ExistentialCondition):
        variables += [par.name for par in axiom.condition.parameters]
    return pddl.Atom(name, variables)


def axiom_conditions(domain):
    for axiom in domain.axioms:
        yield AxiomConditionProxy(axiom)

# [1] Remove universal quantifications from conditions.
#
# Replace, in a top-down fashion, <forall(vars, phi)> by <not(not-all-phi)>,
# where <not-all-phi> is a new axiom.
#
# <not-all-phi> is defined as <not(forall(vars,phi))>, which is of course
# translated to NNF. The parameters of the new axioms are exactly the free
# variables of <forall(vars, phi)>.
def remove_universal_quantifiers(domain):
    def recurse(condition, is_legality_axiom):
        # Uses new_axioms_by_condition and type_map from surrounding scope.
        if isinstance(condition, pddl.UniversalCondition):
            axiom_condition = condition.negate()
            parameters = sorted(axiom_condition.free_variables())
            typed_parameters = tuple(pddl.TypedObject(v, type_map[v]) for v in parameters)
            axiom = new_axioms_by_condition.get((axiom_condition,
                                                 typed_parameters,
                                                 is_legality_axiom))
            if not axiom:
                condition = recurse(axiom_condition, is_legality_axiom)
                axiom = domain.add_axiom(list(typed_parameters), condition,
                                         is_legality_axiom)
                new_axioms_by_condition[(condition, typed_parameters,
                                         is_legality_axiom)] = axiom
            return pddl.NegatedAtom(axiom.name, parameters)
        else:
            new_parts = [recurse(part, is_legality_axiom) for part in condition.parts]
            return condition.change_parts(new_parts)

    new_axioms_by_condition = {}
    for proxy in tuple(axiom_conditions(domain)):
        # Cannot use generator because we add new axioms on the fly.
        if proxy.condition.has_universal_part():
            type_map = proxy.get_type_map()
            proxy.set(recurse(proxy.condition, proxy.owner.legality_axiom))


# [2] Pull disjunctions to the root of the condition.
#
# After removing universal quantifiers, the (k-ary generalization of the)
# following rules suffice for doing that:
# (1) or(phi, or(psi, psi'))      ==  or(phi, psi, psi')
# (2) exists(vars, or(phi, psi))  ==  or(exists(vars, phi), exists(vars, psi))
# (3) and(phi, or(psi, psi'))     ==  or(and(phi, psi), and(phi, psi'))
def build_DNF(domain):
    def recurse(condition):
        disjunctive_parts = []
        other_parts = []
        for part in condition.parts:
            part = recurse(part)
            if isinstance(part, pddl.Disjunction):
                disjunctive_parts.append(part)
            else:
                other_parts.append(part)
        if not disjunctive_parts:
            return condition

        # Rule (1): Associativity of disjunction.
        if isinstance(condition, pddl.Disjunction):
            result_parts = other_parts
            for part in disjunctive_parts:
                result_parts.extend(part.parts)
            return pddl.Disjunction(result_parts)

        # Rule (2): Distributivity disjunction/existential quantification.
        if isinstance(condition, pddl.ExistentialCondition):
            parameters = condition.parameters
            result_parts = [pddl.ExistentialCondition(parameters, (part,))
                            for part in disjunctive_parts[0].parts]
            return pddl.Disjunction(result_parts)

        # Rule (3): Distributivity disjunction/conjunction.
        assert isinstance(condition, pddl.Conjunction)
        result_parts = [pddl.Conjunction(other_parts)]
        while disjunctive_parts:
            previous_result_parts = result_parts
            result_parts = []
            parts_to_distribute = disjunctive_parts.pop().parts
            for part1 in previous_result_parts:
                for part2 in parts_to_distribute:
                    result_parts.append(pddl.Conjunction((part1, part2)))
        return pddl.Disjunction(result_parts)

    for proxy in axiom_conditions(domain):
        if proxy.condition.has_disjunction():
            proxy.set(recurse(proxy.condition).simplified())

# [3] Split conditions at the outermost disjunction.
def split_disjunctions(domain):
    for proxy in tuple(axiom_conditions(domain)):
        # Cannot use generator directly because we add/delete entries.
        if isinstance(proxy.condition, pddl.Disjunction):
            for part in proxy.condition.parts:
                new_proxy = proxy.clone_owner()
                new_proxy.set(part)
                new_proxy.register_owner(domain)
            proxy.delete_owner(domain)

# [4] Pull existential quantifiers out of conjunctions and group them.
#
# After removing universal quantifiers and creating the disjunctive form,
# only the following (representatives of) rules are needed:
# (1) exists(vars, exists(vars', phi))  ==  exists(vars + vars', phi)
# (2) and(phi, exists(vars, psi))       ==  exists(vars, and(phi, psi)),
#       if var does not occur in phi as a free variable.
def move_existential_quantifiers(domain):
    def recurse(condition):
        existential_parts = []
        other_parts = []
        for part in condition.parts:
            part = recurse(part)
            if isinstance(part, pddl.ExistentialCondition):
                existential_parts.append(part)
            else:
                other_parts.append(part)
        if not existential_parts:
            return condition

        # Rule (1): Combine nested quantifiers.
        if isinstance(condition, pddl.ExistentialCondition):
            new_parameters = condition.parameters + existential_parts[0].parameters
            new_parts = existential_parts[0].parts
            return pddl.ExistentialCondition(new_parameters, new_parts)

        # Rule (2): Pull quantifiers out of conjunctions.
        assert isinstance(condition, pddl.Conjunction)
        new_parameters = []
        new_conjunction_parts = other_parts
        for part in existential_parts:
            new_parameters += part.parameters
            new_conjunction_parts += part.parts
        new_conjunction = pddl.Conjunction(new_conjunction_parts)
        return pddl.ExistentialCondition(new_parameters, (new_conjunction,))

    for proxy in axiom_conditions(domain):
        if proxy.condition.has_existential_part():
            proxy.set(recurse(proxy.condition).simplified())


# [5] Drop existential quantifiers from axioms, turning them
#     into parameters.

def eliminate_existential_quantifiers_from_axioms(domain):
    # Note: This is very redundant with the corresponding method for
    # actions and could easily be merged if axioms and actions were
    # unified.
    for axiom in domain.axioms:
        precond = axiom.condition
        if isinstance(precond, pddl.ExistentialCondition):
            # Copy parameter list, since it can be shared with
            # parameter lists of other versions of this axiom (e.g.
            # created when splitting up disjunctive preconditions).
            axiom.parameters = list(axiom.parameters)
            axiom.parameters.extend(precond.parameters)
            axiom.condition = precond.parts[0]


# Combine Steps [1], [2], [3], [4], [5]
def normalize_axioms(domain):
    remove_universal_quantifiers(domain)
    build_DNF(domain)
    split_disjunctions(domain)
    move_existential_quantifiers(domain)
    eliminate_existential_quantifiers_from_axioms(domain)
