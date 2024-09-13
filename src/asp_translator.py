import pddl

from pddl import Predicate
from pddl import Type
from pddl import TypedObject


def get_forbidden_symbols(string: str):
    # clingo allows the following symbols for constants and variables: [A-Za-z0-9_’]
    allowed_symbols = [chr(c) for c in range(ord('a'), ord('z')+1)] + [chr(c)
            for c in range(ord('A'), ord('Z')+1)] + [str(n) for n in range(10)] + ['_', '’']
    return [sym for sym in string if sym not in allowed_symbols]


def get_index_of_first_non_underscore(string: str):
    for i in range(len(string)):
        if string[i] != '_':
            return i

def translate_to_asp_predicate(pddl_predicate_name: str):
    asp_predicate = pddl_predicate_name

    forbidden_symbols = get_forbidden_symbols(pddl_predicate_name)
    if len(forbidden_symbols) >= 1:
        # TODO is there a better option than just removing forbidden symbols?
        # TODO replace, instead of remove, hyphen '-' because it occurs
        # frequently in PDDL domains?
        print(f"WARNING: Predicate {pddl_predicate_name} contains the following forbidden symbols that are removed: {forbidden_symbols}")
        asp_predicate = ''.join([c for c in pddl_predicate_name if c not in
            forbidden_symbols])

    # check if first character, potentially after a sequence of underscores
    # '_', is a letter, if not add prefix 'pred_'
    first_non_underscore = get_index_of_first_non_underscore(asp_predicate)
    if not asp_predicate[first_non_underscore].isalpha():
        asp_predicate = "pred_" + asp_predicate

    # Predicates in clingo must start with a lower case letter. We transform
    # the entire predicate to lower case so that "pred", "PRED" and "Pred"
    # (identical predicates in PDDL) are mapped to the same transformed string.
    return asp_predicate.lower()


def translate_to_asp_object(pddl_object: str):
    if all(c.isdigit() for c in pddl_object):
        # objects in clingo can be (positive) integers
        return pddl_object

    asp_object = pddl_object
    forbidden_symbols = get_forbidden_symbols(pddl_object)
    if len(forbidden_symbols) >= 1:
        # TODO is there a better option than just removing forbidden symbols?
        # TODO replace, instead of remove, hyphen '-' because it occurs
        # frequently in PDDL domains?
        print(f"WARNING: Object {pddl_object} contains the following forbidden symbols that are removed: {forbidden_symbols}")
        asp_object = ''.join([c for c in pddl_object if c not in
            forbidden_symbols])

    # check if first character, potentially after a sequence of underscores
    # '_', is a letter, if not add prefix 'obj_'
    first_non_underscore = get_index_of_first_non_underscore(asp_object)
    if not asp_object[first_non_underscore].isalpha():
        asp_object = "obj_" + asp_object
    
    # Objects in clingo must start with a lower case letter. We transform the
    # entire object to lower case so that "obj", "OBJ" and "Obj" (identical
    # objects in PDDL) are mapped to the same transformed string.
    return asp_object.lower()


def translate_to_asp_variable(pddl_variable: str):
    assert pddl_variable[0] == "?"
    asp_variable = pddl_variable[1:]

    forbidden_symbols = get_forbidden_symbols(asp_variable)
    if len(forbidden_symbols) >= 1:
        # TODO is there a better option than just removing forbidden symbols?
        # TODO replace, instead of remove, hyphen '-' because it occurs
        # frequently in PDDL domains?
        print(f"WARNING: Variable {asp_variable} contains the following forbidden symbols that are removed: {forbidden_symbols}")
        asp_variable = ''.join([c for c in asp_variable if c not in
            forbidden_symbols])

    # check if first character, potentially after a sequence of underscores
    # '_', is a letter, if not add prefix 'Var_'
    first_non_underscore = get_index_of_first_non_underscore(asp_variable)
    if not asp_variable[first_non_underscore].isalpha():
        asp_variable = "Var_" + asp_variable
    
    # Variables in clingo must start with a upper case letter. We transform the
    # entire variable to lower case so that "var", "VAR" and "Var" (identical
    # variables in PDDL) are mapped to the same transformed string.
    return asp_variable.upper()


# transforms objects and variables
def translate_to_asp_term(pddl_term: str):
    if pddl_term[0] == "?":
        return translate_to_asp_variable(pddl_term)
    else:
        return translate_to_asp_object(pddl_term)


class ASPGenerator:
    # assumes that domain.axioms are in Datalog form, i. e., rule bodies are
    # (implicitly existentially quantified) conjunctions of literals
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
            object_name = translate_to_asp_object(obj.name)
            if obj.type_name != self.generic_type.name:
                object_type = translate_to_asp_predicate(obj.type_name)
                facts.append(f"{object_type}({object_name}).")
            generic_type = translate_to_asp_predicate(self.generic_type.name)
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
                type_name = translate_to_asp_predicate(t.name)
                head_parts.append(type_name + f"({variables[0]})")

        # add the basic predicates to choice rule
        for p in self.basic_predicates:
            parameters = [variables[i] for i in range(p.get_arity())]
            predicate_name = translate_to_asp_predicate(p.name)
            head_parts.append(predicate_name + "(" + ", ".join(parameters) + ")")
        head = "{" + ", ".join(head_parts) + "}"

        # make rule safe
        generic_type = translate_to_asp_predicate(self.generic_type.name)
        body_parts = [f"{generic_type}({var})" for var in variables]
        body = ", ".join(body_parts)

        rule = f"{head} :- {body}."
        return [rule]


    def generate_axioms(self):
        axioms = [axiom.asp_string(translate_to_asp_predicate, translate_to_asp_term) for axiom in
                self.domain.axioms]

        # integrity constraint that enforces legality
        legality_predicate = translate_to_asp_predicate(self.domain.legality_predicate)
        axioms.append(f":- not {legality_predicate}().")
        return axioms


    def generate_show_statements(self):
        statements = []
        for pred in self.basic_predicates:
            predicate_name = translate_to_asp_predicate(pred.name)
            arity = pred.get_arity()
            statements.append(f"#show {predicate_name}/{arity}.")
        return statements


def translate(domain: pddl.Domain, universe_size=1):
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

