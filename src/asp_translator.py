import pddl

from pddl import Predicate
from pddl import Type
from pddl import TypedObject


def to_asp_predicate(pddl_predicate_name: str):
    # TODO ensure that string adheres to clingo syntax for constants
    # TODO this must be same translation as in pddl.Literal.asp_string
    return pddl_predicate_name.lower()


def to_asp_object(pddl_object: str):
    # TODO ensure that string adheres to clingo syntax for constants or is integer
    
    # constants in clingo start with a lowercase letter
    # (potentially preceded by underscores '_') and may not contain
    # symbols other than those in [A-Za-z0-9_’]
    # TODO thoroughly check for symbols other than those
    #
    # We transform the entire object to lower case so that "obj", "OBJ" and
    # "Obj" (identical objects in PDDL) are mapped to the same transformed
    # string.
    return pddl_object.lower()


def to_asp_variable(pddl_variable: str):
    # variables in clingo start with an uppercase letter
    # (potentially preceded by underscores '_') and may not contain
    # symbols other than those in [A-Za-z0-9_’]
    # TODO thoroughly check for symbols other than those
    
    assert pddl_variable[0] == "?"
    return pddl_variable[1:].upper()

# transforms objects and variables
def to_asp_term(pddl_term: str):
    if pddl_term[0] == "?":
        return to_asp_variable(pddl_term)
    else:
        return to_asp_object(pddl_term)

class ASPGenerator:
    # assumes that domain.axioms are in Datalog form, i. e., rule bodies are
    # (implicitly existentially quantified) conjunctions of literals
    # TODO adhere to clingo-syntax, i. e., predicates must start with lowercase
    # letter, variables with uppercase, dash '-' is not allowed
    def __init__(self, domain: pddl.Domain, universe_size = 1):
        self.domain = domain
        self.universe_size = universe_size
        self.generic_type =  self._get_generic_type()
          # type that all objects share
        self.objects = self._get_objects()
          # list of TypedObject (compared to domain.objects this also includes
          # the task-specific objects)
        self.basic_predicates = self._get_basic_predicates()


    def _get_generic_type(self):
        types = self.domain.types
        if len(types) == 1:
            # all objects have the given type
            return types[0]
        else:
            # all objects have a generic type (the ASP solver decides which object
            # gets which specific type)
            return Type("object")


    def _get_objects(self):
        domain_wide_objects = self.domain.objects 
        task_specific_objects = [TypedObject(str(i), self.generic_type.name) for i in range(1, self.universe_size+1)]
        return domain_wide_objects + task_specific_objects


    def _get_basic_predicates(self):
        # from self.domain.predicates returns those that are basic predicates,
        # exluding equality '='
        predicates = self.domain.predicates
        derived_predicates = [axiom.name for axiom in self.domain.axioms]

        basic_predicates = []
        for pred in predicates:
            if not pred.name in derived_predicates and pred.name != "=":
                basic_predicates.append(pred)
        return basic_predicates


    def generate_type_facts(self):
        # generates a fact for each object specifying that it has the
        # generic type; if it is a domain-wide object with a specific
        # type, a fact for this type is added as well
        facts = []
        for obj in self.objects:
            object_name = to_asp_object(obj.name)
            if obj.type_name != self.generic_type.name:
                object_type = to_asp_predicate(obj.type_name)
                facts.append(f"{object_type}({object_name}).")
            generic_type = to_asp_predicate(self.generic_type.name)
            facts.append(f"{generic_type}({object_name}).")
        return facts


    def generate_choice_predicates_rule(self):
        # generates a choice rule that specifies all predicates which the ASP
        # solver has to choose truth values for (this includes the basic
        # predicates from the PDDL domain, as well as predicates for the types of
        # the domain)
        # TODO break into multiple choice rules (that take argument types into
        # account) for more efficiency?

        max_arity = max(pred.get_arity() for pred in self.basic_predicates)
        variables = [f"Var_{i}" for i in range(1, max_arity + 1)]
        head_parts = []

        # add predicates for PDDL types to choice rule
        types = self.domain.types
        if len(types) > 1:
            for t in types:
                type_name = to_asp_predicate(t.name)
                head_parts.append(type_name + f"({variables[0]})")

        # add the basic predicates to choice rule
        for p in self.basic_predicates:
            arguments = [variables[i] for i in range(p.get_arity())]
            predicate_name = to_asp_predicate(p.name)
            head_parts.append(predicate_name + "(" + ", ".join(arguments) + ")")
        head = "{" + ", ".join(head_parts) + "}"

        # make rule safe
        generic_type = to_asp_predicate(self.generic_type.name)
        body_parts = [f"{generic_type}({var})" for var in variables]
        body = ", ".join(body_parts)

        rule = f"{head} :- {body}."
        return [rule]


    def generate_axioms(self):
        axioms = [axiom.asp_string(to_asp_predicate, to_asp_term) for axiom in self.domain.axioms]

        # integrity constraint that enforces legality
        legality_predicate = to_asp_predicate(self.domain.legality_predicate)
        axioms.append(f":- not {legality_predicate}().")
        return axioms


    def generate_show_statements(self):
        statements = []
        for pred in self.basic_predicates:
            predicate_name = to_asp_predicate(pred.name)
            arity = pred.get_arity()
            statements.append(f"#show {predicate_name}/{arity}.")
        return statements


def translate(domain, universe_size=1):
    if universe_size <= 0:
        print("Size of universe must be at least 1.")
        sys.exit(1)

    asp_generator = ASPGenerator(domain, universe_size)
    translated_parts = []
    translated_parts += asp_generator.generate_type_facts()
    translated_parts += asp_generator.generate_choice_predicates_rule()
    translated_parts += asp_generator.generate_axioms()
    translated_parts += asp_generator.generate_show_statements()

    translated_domain = '\n'.join(translated_parts)
    return translated_domain

