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

    def asp_string(self, predicate_conversion, term_conversion):
        assert type(self.condition) in [conditions.Conjunction,
                conditions.Atom, conditions.NegatedAtom]
        head_parameters = self.parameters[:self.num_external_parameters]
        head_parameters_string = ", ".join(term_conversion(param.name) for param in
                head_parameters)
        head = f"{self.name}({head_parameters_string})"
        # TODO what to do if parameters have a type other than the generic
        # "object"? add an atom for this to the condition?
        body = self.condition.asp_string(predicate_conversion, term_conversion)
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
