from typing import List

from . import conditions
from .conditions import Atom, Condition, Literal
from .pddl_types import TypedObject


class Axiom:
    def __init__(self, name: str, parameters: List[TypedObject],
                 num_external_parameters: int, condition: Condition,
                 legality_axiom: bool, cardinality : List[int]|None = None):
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
        self.cardinality = cardinality

    def asp_string(self, predicate_conversion, term_conversion):
        assert type(self.condition) in [conditions.Conjunction,
                conditions.Atom, conditions.NegatedAtom]

        head_parameters = self.parameters[:self.num_external_parameters]
        head_parameters_string = ", ".join(term_conversion(param.name) for param in
                head_parameters)
        head = f"{predicate_conversion(self.name)}({head_parameters_string})"

        body = self.condition.asp_string(predicate_conversion, term_conversion)
        # ensure typing of parameters and make rule safe
        if len(self.parameters) >= 1:
            parameter_type_atoms = ", ".join(
                    [f"{predicate_conversion(param.type_name)}({term_conversion(param.name)})"
                        for param in self.parameters])
            if self.cardinality:
                body = f"{{ {body + ": " + parameter_type_atoms} }} = {self.cardinality[0]}"  # TODO: In fact, currently the cardinality for all variables are the same
            else:
                body = body + ", " + parameter_type_atoms

        rule = f"{head} :- {body}."
        return rule

    def dump(self):
        args = map(str, self.parameters[:self.num_external_parameters])
        legality = "Legality " if self.legality_axiom else ""
        card = "Counting " if self.cardinality else ""
        card_list = f" {tuple(self.cardinality)} " if self.cardinality else ""
        print("%s%sAxiom %s(%s)%s" % (legality, card, self.name, ", ".join(args), card_list))
        self.condition.dump()

    def uniquify_variables(self):
        self.type_map = {par.name: par.type_name for par in self.parameters}
        self.condition = self.condition.uniquify_variables(self.type_map)
