from typing import List

from . import conditions
from .conditions import Atom, Condition, Literal
from .pddl_types import TypedObject


class Axiom:
    def __init__(self, name: str, parameters: List[TypedObject],
                 num_external_parameters: int, condition: Condition,
                 legality_axiom: bool):
        # For an explanation of num_external_parameters, see the
        # related Action class. Note that num_external_parameters
        # always equals the arity of the derived predicate.
        assert 0 <= num_external_parameters <= len(parameters)
        self.name = name
        self.parameters = parameters
        self.num_external_parameters = num_external_parameters
        self.condition = condition
        self.legality_axiom = legality_axiom
        self.uniquify_variables()

    def asp_string(self):
        assert type(self.condition) in [conditions.Conjunction,
                conditions.Atom, conditions.NegatedAtom]
        head_parameters = self.parameters[:self.num_external_parameters]
        head_parameters_string = ", ".join(param.name for param in
                head_parameters) # TODO param.name needs to adhere to clingo syntax
        head = f"{self.name}({head_parameters_string})"
        # TODO what to do if parameters have a type other than the generic
        # "object"? add an atom for this to the condition?
        if type(self.condition) is conditions.Conjunction:
            body_parts =  []
            for part in self.condition.parts:
                assert type(part) in [conditions.Atom, conditions.NegatedAtom]
                body_parts.append(part.asp_string())
            body = ", ".join(body_parts)
        else: # Atom or NegatedAtom
            body = self.condition.asp_string()
        rule = f"{head} :- {body}."
        return rule

    def dump(self):
        args = map(str, self.parameters[:self.num_external_parameters])
        legality = "Legality " if self.legality_axiom else ""
        print("%sAxiom %s(%s)" % (legality, self.name, ", ".join(args)))
        self.condition.dump()

    def uniquify_variables(self):
        self.type_map = {par.name: par.type_name for par in self.parameters}
        self.condition = self.condition.uniquify_variables(self.type_map)
