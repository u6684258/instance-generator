from collections import defaultdict
from itertools import combinations
import sys

from . import pddl


def replace_special_symbols(string: str):
    # symbols '@' and '-' are replaced with '_AT_' and '_DASH_', respectively
    output = string
    for replacement in [('@', '_AT_'), ('-', '_DASH_')]:
        output = output.replace(*replacement)
    return output


def get_forbidden_symbols(string: str):
    # clingo allows the following symbols for constants and variables: [A-Za-z0-9_’]
    allowed_symbols = [chr(c) for c in range(ord('a'), ord('z')+1)] + [chr(c)
            for c in range(ord('A'), ord('Z')+1)] + [str(n) for n in range(10)] + ['_', '’']
    return [sym for sym in string if sym not in allowed_symbols]


def get_index_of_first_non_underscore(string: str):
    for i in range(len(string)):
        if string[i] != '_':
            return i
    return None


def translate_to_asp_predicate(pddl_predicate_name: str):
    asp_predicate = pddl_predicate_name.lower()
      # Predicates in clingo must start with a lower case letter. We transform
      # the entire predicate to lower case so that "pred", "PRED" and "Pred"
      # (identical predicates in PDDL) are mapped to the same transformed
      # string.

    # The Fast Downward parser adds the prefix "type@" internally if a type is
    # used as a predicate. For the translation to ASP we need to undo this
    # treatment.
    if asp_predicate.startswith("type@"):
        asp_predicate = asp_predicate.replace("type@", "", 1)

    # replace symbols '@' and '-' (these two are treated explicitly because the
    # Fast Downward parser allows / adds them)
    forbidden_symbols = get_forbidden_symbols(asp_predicate)
    if '@' in forbidden_symbols or '-' in forbidden_symbols:
        asp_predicate = replace_special_symbols(asp_predicate)
        forbidden_symbols = [sym for sym in forbidden_symbols if sym not in ['@',
            '-']]
    assert(len(forbidden_symbols) == 0)

    # check if first character, potentially after a sequence of underscores
    # '_', is a letter, if not add prefix 'pred_'
    first_non_underscore = get_index_of_first_non_underscore(asp_predicate)
    if first_non_underscore is None or not asp_predicate[first_non_underscore].isalpha():
        asp_predicate = "pred_" + asp_predicate

    return asp_predicate


def translate_to_asp_object(pddl_object: str):
    if all(c.isdigit() for c in pddl_object):
        # objects in clingo can be integers
        return pddl_object
    asp_object = pddl_object.lower()
      # Objects in clingo must start with a lower case letter. We transform the
      # entire object to lower case so that "obj", "OBJ" and "Obj" (identical
      # objects in PDDL) are mapped to the same transformed string.

    # replace forbidden symbols '@' and '-'
    forbidden_symbols = get_forbidden_symbols(asp_object)
    if '@' in forbidden_symbols or '-' in forbidden_symbols:
        asp_object = replace_special_symbols(asp_object)
        forbidden_symbols = [sym for sym in forbidden_symbols if sym not in ['@',
            '-']]
    assert(len(forbidden_symbols) == 0)

    # check if first character, potentially after a sequence of underscores
    # '_', is a letter, if not add prefix 'obj_'
    first_non_underscore = get_index_of_first_non_underscore(asp_object)
    if first_non_underscore is None or not asp_object[first_non_underscore].isalpha():
        asp_object = "obj_" + asp_object
    
    return asp_object


def translate_to_asp_variable(pddl_variable: str):
    assert pddl_variable[0] == "?"
    asp_variable = pddl_variable[1:].upper()
      # Variables in clingo must start with a upper case letter. We transform
      # the entire variable to lower case so that "var", "VAR" and "Var"
      # (identical variables in PDDL) are mapped to the same transformed
      # string.

    # replace forbidden symbols '@' and '-'
    forbidden_symbols = get_forbidden_symbols(asp_variable)
    if '@' in forbidden_symbols or '-' in forbidden_symbols:
        asp_variable = replace_special_symbols(asp_variable)
        forbidden_symbols = [sym for sym in forbidden_symbols if sym not in ['@',
            '-']]
    assert(len(forbidden_symbols) == 0)

    # check if first character, potentially after a sequence of underscores
    # '_', is a letter, if not add prefix 'Var_'
    first_non_underscore = get_index_of_first_non_underscore(asp_variable)
    if first_non_underscore is None or not asp_variable[first_non_underscore].isalpha():
        asp_variable = "Var_" + asp_variable
    
    return asp_variable


def translate_to_asp_term(pddl_term: str):
    # transforms objects and variables
    if pddl_term[0] == "?":
        return translate_to_asp_variable(pddl_term)
    else:
        return translate_to_asp_object(pddl_term)


class ASPGenerator:
    # assumes that domain.axioms are in Datalog form, i. e., rule bodies are
    # (implicitly existentially quantified) conjunctions of literals
    def __init__(self, domain: pddl.Domain, typed_universe: dict,
                 cardinality_constraints: dict):
        self.domain = domain
        self.universe_size = sum([n for t,n in typed_universe.items()])
        self.generic_type =  self._get_generic_type()
          # type that all objects share
        self.objects = self._get_objects(typed_universe)
          # list of TypedObject (compared to domain.objects this also includes
          # the task-specific objects)
        self.basic_predicates = self._get_basic_predicates()
        self.check_cardinality_constraints(cardinality_constraints)
        self.cardinality_constraints = cardinality_constraints


    def _get_generic_type(self):
        types = self.domain.types
        if len(types) == 1:
            # all objects have the given type
            return types[0]
        else:
            # all objects have the generic PDDL type "object"
            return pddl.Type("object")


    def _get_objects(self, typed_universe: dict):
        domain_wide_objects = self.domain.objects 
        object_number = 1
        task_specific_objects = []
        for t,n in typed_universe.items():
            for i in range(n):
                task_specific_objects.append(
                        pddl.TypedObject(str(object_number), t))
                object_number = object_number + 1
        return domain_wide_objects + task_specific_objects


    def _get_basic_predicates(self):
        # from self.domain.predicates returns those that are basic predicates,
        # exluding equality '=' and less-than "<"
        predicates = self.domain.predicates
        derived_predicates = [axiom.name for axiom in self.domain.axioms]

        basic_predicates = []
        for pred in predicates:
            if not pred.name in derived_predicates and \
                    pred.name != "=" and pred.name != "<":
                basic_predicates.append(pred)
        return basic_predicates

    def check_cardinality_constraints(self, cardinality_constraints: dict):
        # check if each key of the given dictionary is a name of a predicate in
        # self.basic_predicates
        # check if the lower and upper bounds given in the items of the
        # dictionary are valid cardinalities
        predicate_names = [p.name for p in self.basic_predicates]
        for predicate_name, interval in cardinality_constraints.items():
            if predicate_name not in predicate_names:
                print(f"Error: Predicate {predicate_name} mentioned in the cardinality constraints is not mentioned as a basic predicate in the domain file.")
                sys.exit(1)

            predicate = next(p for p in self.basic_predicates if \
                    p.name == predicate_name)
            max_cardinality = predicate.get_arity()** len(self.basic_predicates)
            if interval[0] > max_cardinality:
                print(f"Error: The lower cardinality bound of predicate {predicate_name} is given as {interval[0]} but can be at most {max_cardinality}.")
                sys.exit(1)
            if interval[1] < -1:
                print(f"Error: The upper cardinality bound of predicate {predicate_name} is given as {interval[1]} but must be at least 0 (or alternatively, default value -1).")
                sys.exit(1)


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
        # generates choice rules that specify which predicates the ASP
        # solver has to choose truth values for (this includes the basic
        # predicates from the PDDL domain, as well as predicates for the types
        # of the domain)
        # basic predicates that are mentioned in the cardinality constraints
        # (which are provided by the user) have their own choice rules that
        # reflect the respective cardinality constraints
        # TODO break generic choice rule further up (to take argument types
        # into account) for more efficiency? (if we do this, we can probably
        # remove the parameter type axioms)

        max_arity = max(pred.get_arity() for pred in self.basic_predicates)
        variables = [f"Var_{i}" for i in range(1, max_arity + 1)]
        choice_rules = []

        # choice rules for basic predicates that are mentioned in the
        # cardinality constraints
        covered_predicates = []
        for pred_name, interval in self.cardinality_constraints.items():
            pred = next(p for p in self.basic_predicates if p.name == pred_name)
            parameter_string = ", ".join(variables[:pred.get_arity()])
            translated_pred = translate_to_asp_predicate(pred_name) + \
                    "(" + parameter_string + ")"

            type_predicates = []
            for i in range(pred.get_arity()):
                type_pred_name = translate_to_asp_predicate(
                        pred.arguments[i].type_name)
                type_predicates.append(f"{type_pred_name}({variables[i]})")
            condition = ", ".join(type_predicates)

            lower_bound = f"{interval[0]} <= " if interval[0] != -1 else ""
            upper_bound = f" <= {interval[1]}" if interval[1] != -1 else ""

            choice_rules.append(f"{lower_bound}{{{translated_pred} : {condition}}}{upper_bound}.")
            covered_predicates.append(pred_name)

        # generic choice rule that covers the remaining basic predicates
        head_parts = []

        # add predicates for PDDL types to generic choice rule
        types = self.domain.types
        if len(types) > 1:
            for t in types:
                type_name = translate_to_asp_predicate(t.name)
                head_parts.append(type_name + f"({variables[0]})")

        # add the remaining basic predicates to generic choice rule
        for p in self.basic_predicates:
            if p.name in covered_predicates:
                continue
            parameters = [variables[i] for i in range(p.get_arity())]
            predicate_name = translate_to_asp_predicate(p.name)
            head_parts.append(predicate_name + "(" + ", ".join(parameters) + ")")
        head = "{" + "; ".join(head_parts) + "}"

        # make generic choice rule safe
        generic_type = translate_to_asp_predicate(self.generic_type.name)
        new_max_arity = max(pred.get_arity() for pred in self.basic_predicates \
                            if pred.name not in covered_predicates)
        body_parts = [f"{generic_type}({var})" for var in \
                      variables[:new_max_arity]]
        body = ", ".join(body_parts)
        choice_rules.append(f"{head} :- {body}.")

        return choice_rules


    def generate_axioms(self):
        axioms = [axiom.asp_string(translate_to_asp_predicate,
            translate_to_asp_term) for axiom in self.domain.axioms]

        axioms.extend(self.generate_parameter_type_axioms())
        axioms.extend(self.generate_type_hierarchy_axioms())

        # integrity constraint that enforces legality
        legality_predicate = translate_to_asp_predicate(
                self.domain.legality_predicate)
        axioms.append(f":- not {legality_predicate}().")
        return axioms


    def generate_parameter_type_axioms(self):
        # generates axioms ensuring that the basic predicates are instantiated
        # only with objects of correct types
        axioms = []
        for pred in self.basic_predicates:
            pred_name = translate_to_asp_predicate(pred.name)
            pred_params = ', '.join([translate_to_asp_term(param.name) for
                                     param in pred.arguments])
            pred_atom = f"{pred_name}({pred_params})"
            for param in pred.arguments:
                param_name = translate_to_asp_term(param.name)
                param_type = translate_to_asp_predicate(param.type_name)
                axioms.append(f":- {pred_atom}, not {param_type}({param_name}).")
        return axioms


    def generate_type_hierarchy_axioms(self):
        # generates axioms ensuring that the type-predicates comply with the
        # type hierarchy of the domain
        direct_subtypes = defaultdict(set)
        axioms = []
        for t in self.domain.types:
            if t.basetype_name is not None:
                direct_subtypes[t.basetype_name].add(t.name)
                type_name = translate_to_asp_predicate(t.name)
                basetype_name = translate_to_asp_predicate(t.basetype_name)
                axioms.append(f":- {type_name}(X), not {basetype_name}(X).")
                  # if t has a supertype (a basetype), all objects of type t
                  # must also have the supertype
        for basetype, subtypes in direct_subtypes.items():
            for t1, t2 in combinations(subtypes, 2):
                translated_t1 = translate_to_asp_predicate(t1)
                translated_t2 = translate_to_asp_predicate(t2)
                axioms.append(f":- {translated_t1}(X), {translated_t2}(X).")
                  # types with the same direct supertype (same basetype) are
                  # mutually exclusive
        return axioms


    def generate_show_statements(self):
        statements = []
        for t in self.domain.types:
            predicate_name = translate_to_asp_predicate(t.name)
            statements.append(f"#show {predicate_name}/1.")

        for pred in self.basic_predicates:
            predicate_name = translate_to_asp_predicate(pred.name)
            arity = pred.get_arity()
            statements.append(f"#show {predicate_name}/{arity}.")
        return statements


def translate(domain: pddl.Domain, universe: dict,
                          cardinality_constraints: dict):
    if sum([n for t,n in universe.items()]) <= 0:
        print("Error: Universe must contain at least one object.")
        sys.exit(1)
    pddl_types = [t.name for t in domain.types]
    for t in universe.keys():
        if not t in pddl_types:
            print(f"Error: Type {t} mentioned in the universe is not mentioned as a type in the domain file.")
            sys.exit(1)

    asp_generator = ASPGenerator(domain, universe, cardinality_constraints)
    translated_parts = []
    translated_parts += asp_generator.generate_type_facts()
    translated_parts += asp_generator.generate_choice_predicates_rule()
    translated_parts += asp_generator.generate_axioms()
    translated_parts += asp_generator.generate_show_statements()

    translated_domain = '\n'.join(translated_parts)
    return translated_domain

