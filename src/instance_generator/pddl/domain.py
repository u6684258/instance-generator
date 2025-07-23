from typing import List, Union, Set

from . import axioms
from . import predicates
from .axioms import Axiom
from .conditions import Atom, Condition
from .functions import Function
from .pddl_types import Type, TypedObject
from .predicates import Predicate

class Domain:
    def __init__(self, domain_name: str,
                 legality_predicate: str,
                 requirements: "Requirements",
                 types: List[Type], objects: List[TypedObject], predicates:
                 List[Predicate], functions: List[Function],
                 goal: Condition,
                 axioms: List[Axiom],
                 affected_predicates: Set[str]) -> None:
        self.domain_name = domain_name
        self.legality_predicate = legality_predicate
        self.requirements = requirements
        self.types = types
        self.objects = objects
        self.predicates = predicates
        self.functions = functions
        self.goal = goal
        self.axioms = axioms
        self.affected_predicates = affected_predicates
        self.axiom_counter = 0

    def add_axiom(self, parameters, condition, legality):
        name = "new-axiom@%d" % self.axiom_counter
        self.axiom_counter += 1
        axiom = axioms.Axiom(name, parameters, len(parameters), condition,
                             legality)
        self.predicates.append(predicates.Predicate(name, parameters))
        self.axioms.append(axiom)
        return axiom

    def dump(self):
        print(f"Domain %s [%s]" % (
            self.domain_name, self.requirements))
        print(f"Legality predicate: {self.legality_predicate}")
        print("Types:")
        for type in self.types:
            print("  %s" % type)
        print("Objects:")
        for obj in self.objects:
            print("  %s" % obj)
        print("Predicates:")
        for pred in self.predicates:
            print("  %s" % pred)
        print("Functions:")
        for func in self.functions:
            print("  %s" % func)
        print("Goal:")
        self.goal.dump()
        if self.axioms:
            print("Axioms:")
            for axiom in self.axioms:
                axiom.dump()
        print("Affected predicates:")
        print(self.affected_predicates)


REQUIREMENT_LABELS = [
    ":strips", ":adl", ":typing", ":negation", ":equality",
    ":negative-preconditions", ":disjunctive-preconditions",
    ":existential-preconditions", ":universal-preconditions",
    ":quantified-preconditions", ":conditional-effects",
    ":derived-predicates", ":action-costs"
]


class Requirements:
    def __init__(self, requirements: List[str]):
        self.requirements = requirements
        for req in requirements:
            if req not in REQUIREMENT_LABELS:
                raise ValueError(f"Invalid requirement. Got: {req}\n"
                                 f"Expected: {', '.join(REQUIREMENT_LABELS)}")
    def __str__(self):
        return ", ".join(self.requirements)
